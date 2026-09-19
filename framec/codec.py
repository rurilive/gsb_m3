"""帧编解码器：Encoder 打帧，Decoder.feed 增量解码（跨包缓冲）。

线格式（多字节字段统一大端）：
    magic(2)=b"FC" | type(1) | flags(1)=保留必须 0 | length(2) | seq(4)
    | payload(length) | crc32(4)，CRC 覆盖从 magic 到 payload 的全部字节。

feed 的容错语义：凑齐整帧才输出；帧头非法（magic/flags/声明长度）抛
HeaderError 且不消费缓冲；CRC 失败抛 CrcError，该帧字节已消费、流可继续；
类型码未注册的帧静默跳过（前向兼容）；载荷校验或解码失败抛 PayloadError，
该帧字节已消费。
"""

import struct
import zlib

from framec.errors import CrcError, FrameError, HeaderError, UnknownTypeError
from framec.registry import HEADER_LEN, MAGIC, MAX_PAYLOAD, REGISTRY, FrameType


class Frame:
    """解码出的一帧。"""

    __slots__ = ("type_code", "type_name", "seq", "value")

    def __init__(self, type_code, type_name, seq, value):
        self.type_code = type_code
        self.type_name = type_name
        self.seq = seq
        self.value = value

    def __repr__(self):
        return "Frame<%s seq=%d value=%r>" % (self.type_name, self.seq, self.value)


class Encoder:
    """打帧器。seq 从 seq_start 起自增；ftype 缺省时按值类型自动识别。"""

    def __init__(self, seq_start=1):
        self._seq = seq_start

    def encode(self, value, ftype=None):
        """编码一帧字节。ftype 可为 FrameType 实例/子类或已注册的类型码。"""
        ft = self._pick(value, ftype)
        payload = ft.encode(value)
        ft.validate(payload)
        seq = self._seq
        self._seq += 1
        head = MAGIC + struct.pack(">BBHI", ft.TYPE, 0, len(payload), seq)
        body = head + payload
        return body + struct.pack(">I", zlib.crc32(body))

    def _pick(self, value, ftype):
        if isinstance(ftype, FrameType):
            return ftype
        if isinstance(ftype, type) and issubclass(ftype, FrameType):
            return ftype()
        if isinstance(ftype, int):
            ft = REGISTRY.get(ftype)
            if ft is None:
                raise UnknownTypeError("未注册的类型码: %#04x" % ftype)
            return ft
        if ftype is None:
            if isinstance(value, str):
                return REGISTRY[0x01]
            if isinstance(value, dict):
                return REGISTRY[0x02]
            raise FrameError("无法推断帧类型，请显式传 ftype")
        raise FrameError("ftype 类型不支持: %r" % (ftype,))


class Decoder:
    """喂入式解码：数据可任意切分，凑齐完整帧才输出。"""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, chunk):
        """喂入字节，返回这次完整解出的 Frame 列表。"""
        self._buf += bytes(chunk)
        frames = []
        while True:
            frame = self._try_parse()
            if frame is None:
                return frames
            frames.append(frame)

    def _try_parse(self):
        buf = self._buf
        if len(buf) < HEADER_LEN:
            return None
        if bytes(buf[:2]) != MAGIC:
            raise HeaderError("magic 不匹配: %r" % bytes(buf[:2]))
        type_code = buf[2]
        flags = buf[3]
        if flags != 0:
            raise HeaderError("保留位非 0: %#04x" % flags)
        length, seq = struct.unpack(">HI", buf[4:10])
        if length > MAX_PAYLOAD:
            raise HeaderError("声明长度超上限: %d" % length)
        total = HEADER_LEN + length + 4
        if len(buf) < total:
            return None
        body = bytes(buf[:HEADER_LEN + length])
        crc = int.from_bytes(buf[HEADER_LEN + length:total], "big")
        del self._buf[:total]
        if zlib.crc32(body) != crc:
            raise CrcError("CRC 校验失败 @ seq=%d" % seq)
        ft = REGISTRY.get(type_code)
        if ft is None:
            return self._try_parse()  # 类型码未注册：按前向兼容跳过该帧
        payload = body[HEADER_LEN:]
        ft.validate(payload)
        return Frame(ft.TYPE, ft.NAME, seq, ft.decode(payload))
