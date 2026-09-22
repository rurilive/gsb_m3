"""链路帧的编解码和按字节流拆帧。

头固定 8 字节大端：stream_id(u32)、kind(u8)、flags(u8)、length(u16)，负载
跟在后面，上限 MAX_FRAME_PAYLOAD，写超了直接拒；读的时候头里的 length 一
超上限就报错，不等人把负载喂满。0 号流留给连接级帧，fin 和 reset 不带负载，
window_update 的负载是 4 字节大端无符号的额度。
"""

import struct

from linkmux.errors import FrameError

HEADER_SIZE = 8
HEADER = struct.Struct(">IBBH")
MAX_FRAME_PAYLOAD = 1024
DEFAULT_MAX_FRAME_PAYLOAD = MAX_FRAME_PAYLOAD
WINDOW_PAYLOAD_SIZE = 4

KIND_DATA = 1
KIND_WINDOW_UPDATE = 2
KIND_FIN = 3
KIND_RESET = 4
KIND_PING = 5
KIND_NAMES = {KIND_DATA: "data", KIND_WINDOW_UPDATE: "window_update", KIND_FIN: "fin",
              KIND_RESET: "reset", KIND_PING: "ping"}

CONNECTION_STREAM_ID = 0
CONNECTION_KINDS = (KIND_PING,)
EMPTY_PAYLOAD_KINDS = (KIND_FIN, KIND_RESET)
MAX_STREAM_ID = 0xFFFFFFFF
MAX_FLAGS = 0xFF
_WINDOW = struct.Struct(">I")


def pack_window(credit):
    """把一份窗口额度编成 window_update 的负载。"""
    if not isinstance(credit, int) or isinstance(credit, bool) or not 0 <= credit <= MAX_STREAM_ID:
        raise FrameError("窗口额度要在 32 位无符号范围内: %r" % (credit,), field="window")
    return _WINDOW.pack(credit)


def unpack_window(payload):
    """把 window_update 的负载解成窗口额度。"""
    if len(payload) != WINDOW_PAYLOAD_SIZE:
        raise FrameError("window_update 负载要 %d 字节，收到 %d 字节" % (WINDOW_PAYLOAD_SIZE, len(payload)),
                         field="length")
    return _WINDOW.unpack(payload)[0]


class Frame(object):
    """一帧，由流号、类型、标志位和负载组成。"""

    __slots__ = ("stream_id", "kind", "flags", "payload")

    def __init__(self, stream_id, kind, payload=b"", flags=0):
        self.stream_id = stream_id
        self.kind = kind
        self.flags = flags
        self.payload = bytes(payload)

    @property
    def kind_name(self):
        return KIND_NAMES.get(self.kind, "kind-%d" % (self.kind,))

    def __eq__(self, other):
        return (isinstance(other, Frame) and self.stream_id == other.stream_id
                and self.kind == other.kind and self.flags == other.flags
                and self.payload == other.payload)

    def __repr__(self):
        return "Frame(stream=%d, kind=%s, flags=%d, payload=%d bytes)" % (
            self.stream_id, self.kind_name, self.flags, len(self.payload))


def check_frame(frame, max_payload=DEFAULT_MAX_FRAME_PAYLOAD):
    """校验一帧的字面约束，不合法抛 FrameError。"""
    if not isinstance(frame.stream_id, int) or isinstance(frame.stream_id, bool) \
            or not 0 <= frame.stream_id <= MAX_STREAM_ID or not isinstance(frame.flags, int) \
            or not 0 <= frame.flags <= MAX_FLAGS:
        raise FrameError("stream_id 或 flags 超出范围: %r" % (frame,), field="stream_id")
    if frame.kind not in KIND_NAMES:
        raise FrameError("未知的帧类型: %r" % (frame.kind,), field="kind")
    if frame.stream_id == CONNECTION_STREAM_ID and frame.kind not in CONNECTION_KINDS:
        raise FrameError("0 号流只留给连接级帧", field="stream_id")
    if frame.kind == KIND_WINDOW_UPDATE and len(frame.payload) != WINDOW_PAYLOAD_SIZE:
        raise FrameError("window_update 负载要 %d 字节，收到 %d 字节"
                         % (WINDOW_PAYLOAD_SIZE, len(frame.payload)), field="payload")
    if frame.kind in EMPTY_PAYLOAD_KINDS and frame.payload:
        raise FrameError("%s 帧不带负载" % (frame.kind_name,), field="payload")
    if len(frame.payload) > max_payload:
        raise FrameError("负载 %d 字节超过上限 %d" % (len(frame.payload), max_payload), field="length")
    return frame


def pack_frame(frame, max_payload=DEFAULT_MAX_FRAME_PAYLOAD):
    """把一帧编成字节。"""
    check_frame(frame, max_payload)
    return HEADER.pack(frame.stream_id, frame.kind, frame.flags, len(frame.payload)) + frame.payload


def unpack_frame(raw, max_payload=DEFAULT_MAX_FRAME_PAYLOAD):
    """把一段完整帧的字节解成 Frame。"""
    if len(raw) < HEADER_SIZE:
        raise FrameError("帧头不完整，只有 %d 字节" % (len(raw),), field="header")
    stream_id, kind, flags, length = HEADER.unpack_from(raw, 0)
    if length > max_payload:
        raise FrameError("负载 %d 字节超过上限 %d" % (length, max_payload), field="length")
    if len(raw) != HEADER_SIZE + length:
        raise FrameError("帧长 %d 与头里的 %d 不符" % (len(raw), HEADER_SIZE + length), field="length")
    return check_frame(Frame(stream_id, kind, raw[HEADER_SIZE:], flags), max_payload)


class FrameBuffer(object):
    """把字节流拆成帧：一块一块喂，随便在哪断都行，pending 是留着的尾巴。"""

    def __init__(self, max_payload=DEFAULT_MAX_FRAME_PAYLOAD):
        self._buf = bytearray()
        self._max_payload = max_payload

    @property
    def pending(self):
        return len(self._buf)

    def feed(self, chunk):
        """追加一块字节，返回追加的字节数。"""
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("chunk 需要字节串，收到 %r" % (type(chunk).__name__,))
        self._buf += chunk
        return len(chunk)

    def pop(self):
        """凑齐一帧就取出来，否则返回 None。"""
        if len(self._buf) < HEADER_SIZE:
            return None
        stream_id, kind, flags, length = HEADER.unpack_from(self._buf, 0)
        if length > self._max_payload:
            raise FrameError("负载 %d 字节超过上限 %d" % (length, self._max_payload), field="length")
        if len(self._buf) < HEADER_SIZE + length:
            return None
        payload = bytes(self._buf[HEADER_SIZE:HEADER_SIZE + length])
        del self._buf[:HEADER_SIZE + length]
        return check_frame(Frame(stream_id, kind, payload, flags), self._max_payload)

    def drain(self):
        """把缓冲里已凑齐的帧全取出来。"""
        out = []
        while (frame := self.pop()) is not None:
            out.append(frame)
        return out
