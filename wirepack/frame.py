"""0x81 新帧的模型与编解码。

帧格式（整数一律 LEB128 变长，单个 varint 最多 5 字节）：

    字段        类型      说明
    magic       1 字节    固定 0x81；老记录首字节是 seq 高字节（<= 0x7A），不会撞
    tag         varint    最低位=1 表示 payload 里再套了一层帧
    payload_len varint    负载长度前缀，必须 <= MAX_FRAME_SIZE
    payload     字节串    长 payload_len
    ext_count   varint    ext 条目数
    ext 条目    key varint + value_len varint + value 字节串

整帧总长（含 magic）不得超过 MAX_FRAME_SIZE；解码端的缓冲也只按这个
上限保留，长度前缀超上限、varint 超 5 字节都按坏帧处理。
"""

from wirepack.errors import DecodeError, EncodeError, WireError

FRAME_MAGIC = 0x81
MAX_FRAME_SIZE = 1 << 16
VARINT_MAX_SIZE = 5
VARINT_MAX = (1 << (VARINT_MAX_SIZE * 7)) - 1

_MAGIC_BYTE = bytes([FRAME_MAGIC])


class _NeedMore(Exception):
    """内部用：当前数据不够解完一帧，field 指出在等哪个字段。"""

    def __init__(self, field):
        super().__init__(field)
        self.field = field


class Frame:
    """一条 0x81 新帧。payload 是字节串，ext 是 (key, value) 条目序列。"""

    __slots__ = ("tag", "payload", "ext")

    def __init__(self, tag, payload=b"", ext=()):
        self.tag = tag
        self.payload = bytes(payload)
        self.ext = tuple((key, bytes(value)) for key, value in ext)

    @property
    def nested(self):
        """tag 最低位：1 表示 payload 里再套了一层帧。"""
        return bool(self.tag & 1)

    def unwrap(self):
        """把嵌套的 payload 解成内层 Frame；tag 最低位为 0 时报错。"""
        if not self.nested:
            raise WireError("tag 最低位为 0，payload 不是嵌套帧")
        frame, next_offset = unpack_frame(self.payload)
        if next_offset != len(self.payload):
            raise DecodeError("嵌套帧尾部残留 %d 字节"
                              % (len(self.payload) - next_offset,),
                              offset=next_offset, field="payload")
        return frame

    def __eq__(self, other):
        if not isinstance(other, Frame):
            return NotImplemented
        return (self.tag, self.payload, self.ext) == (
            other.tag, other.payload, other.ext)

    def __hash__(self):
        return hash((self.tag, self.payload, self.ext))

    def __repr__(self):
        return "Frame(tag=%r, payload=%r, ext=%r)" % (
            self.tag, self.payload, self.ext)


def check_varint_value(value, name):
    """varint 能表达的整数：0 到 VARINT_MAX，布尔不算数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EncodeError("%s 需要整数，收到 %r" % (name, value))
    if not 0 <= value <= VARINT_MAX:
        raise EncodeError("%s 超出 varint 范围 [0, %d]: %r"
                          % (name, VARINT_MAX, value))
    return value


def encode_varint(value):
    """把非负整数编成 LEB128，最长 5 字节。"""
    check_varint_value(value, "varint")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _varint_at(buf, pos, hard_end, limit, field):
    """从 pos 读一个 varint，返回 (value, next_pos)。

    hard_end 是当前实际能读到的位置（数据末尾与帧长上限的较小者）：
    读到 hard_end 还没收尾时，撞的是帧长上限就报错，否则抛 _NeedMore。
    """
    if pos < hard_end:
        byte = buf[pos]
        if byte < 0x80:
            return byte, pos + 1
    elif pos >= limit:
        raise DecodeError("帧长超过上限，字段 %s 越界" % field,
                          field="frame")
    else:
        raise _NeedMore(field)
    result = 0
    shift = 0
    for _ in range(VARINT_MAX_SIZE):
        if pos >= hard_end:
            if pos >= limit:
                raise DecodeError("帧长超过上限，字段 %s 越界" % field,
                                  field="frame")
            raise _NeedMore(field)
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
    raise DecodeError("varint 超过 %d 字节" % VARINT_MAX_SIZE, field=field)


def _frame_at(buf, start, end, max_size):
    """从 start（buf[start] 必须是 0x81）解一帧，返回 (Frame, next_pos)。

    数据不够抛 _NeedMore，帧本身不合法抛 DecodeError（带 field）。
    """
    limit = start + max_size
    hard_end = min(end, limit)
    pos = start + 1
    tag, pos = _varint_at(buf, pos, hard_end, limit, "tag")
    payload_len, pos = _varint_at(buf, pos, hard_end, limit, "payload_len")
    if payload_len > max_size:
        raise DecodeError("payload 长度前缀 %d 超过帧长上限 %d"
                          % (payload_len, max_size), field="payload_len")
    if pos + payload_len > hard_end:
        if pos + payload_len > limit:
            raise DecodeError("帧总长超过上限 %d 字节" % max_size,
                              field="frame")
        raise _NeedMore("payload")
    payload = bytes(buf[pos:pos + payload_len])
    pos += payload_len
    ext_count, pos = _varint_at(buf, pos, hard_end, limit, "ext_count")
    if ext_count > max_size:
        raise DecodeError("ext 条目数 %d 超过帧长上限 %d"
                          % (ext_count, max_size), field="ext_count")
    ext = []
    for index in range(ext_count):
        key, pos = _varint_at(buf, pos, hard_end, limit,
                              "ext[%d].key" % index)
        value_len, pos = _varint_at(buf, pos, hard_end, limit,
                                    "ext[%d].value_len" % index)
        if value_len > max_size:
            raise DecodeError("ext[%d] 值长度前缀 %d 超过帧长上限 %d"
                              % (index, value_len, max_size),
                              field="ext[%d].value_len" % index)
        if pos + value_len > hard_end:
            if pos + value_len > limit:
                raise DecodeError("帧总长超过上限 %d 字节" % max_size,
                                  field="frame")
            raise _NeedMore("ext[%d].value" % index)
        ext.append((key, bytes(buf[pos:pos + value_len])))
        pos += value_len
    return Frame(tag, payload, ext), pos


def pack_frame(frame):
    """把 Frame 编成字节串。值不合法或整帧超上限抛 EncodeError。"""
    tag = check_varint_value(frame.tag, "tag")
    payload = bytes(frame.payload)
    if len(payload) > MAX_FRAME_SIZE:
        raise EncodeError("payload 长 %d 超过帧长上限 %d"
                          % (len(payload), MAX_FRAME_SIZE))
    out = bytearray()
    out.append(FRAME_MAGIC)
    out += encode_varint(tag)
    out += encode_varint(len(payload))
    out += payload
    out += encode_varint(len(frame.ext))
    for key, value in frame.ext:
        check_varint_value(key, "ext key")
        value = bytes(value)
        out += encode_varint(key)
        out += encode_varint(len(value))
        out += value
    if len(out) > MAX_FRAME_SIZE:
        raise EncodeError("整帧长 %d 超过上限 %d"
                          % (len(out), MAX_FRAME_SIZE))
    return bytes(out)


def unpack_frame(data, offset=0, max_size=MAX_FRAME_SIZE):
    """从字节串的 offset 处解出一帧，返回 (Frame, next_offset)。

    数据不够或帧不合法抛 DecodeError，异常带 offset 与 field。
    """
    if offset < 0 or offset >= len(data):
        raise DecodeError("帧不完整: 帧头落在数据外",
                          offset=offset, field="magic")
    if data[offset] != FRAME_MAGIC:
        raise DecodeError("缺帧头 0x%02x，收到 0x%02x"
                          % (FRAME_MAGIC, data[offset]),
                          offset=offset, field="magic")
    try:
        frame, next_pos = _frame_at(data, offset, len(data), max_size)
    except _NeedMore as exc:
        raise DecodeError("帧不完整: 字段 %s 数据不足" % exc.field,
                          offset=offset, field=exc.field)
    except DecodeError as exc:
        if exc.offset is None:
            exc.offset = offset
        raise
    return frame, next_pos
