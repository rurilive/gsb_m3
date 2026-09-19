"""帧类型注册表：类型码 -> FrameType 实例，编解码两端共用。

新增帧类型：继承 FrameType、实现 encode/decode（按需覆写 validate），
调 register() 即可，编解码核心不用动。
"""

from framec.errors import FrameError, PayloadError

MAGIC = b"FC"
MAX_PAYLOAD = 4096
HEADER_LEN = 10   # magic(2) + type(1) + flags(1) + length(2) + seq(4)
CRC_LEN = 4


class FrameType:
    """帧类型基类。"""

    TYPE = 0x00
    NAME = "?"

    def encode(self, value):
        """应用层值 -> 载荷字节。"""
        raise NotImplementedError

    def decode(self, payload):
        """载荷字节 -> 应用层值（已过 CRC 与 validate）。"""
        raise NotImplementedError

    def validate(self, payload):
        """载荷字节级校验，编解码两侧共用；默认只查长度上限。"""
        if len(payload) > MAX_PAYLOAD:
            raise PayloadError("%s 载荷超长: %d 字节" % (self.NAME, len(payload)))


REGISTRY = {}


def register(frame_type):
    """登记帧类型实例，类型码冲突抛 FrameError。"""
    if frame_type.TYPE in REGISTRY:
        raise FrameError("类型码冲突: %#04x" % frame_type.TYPE)
    REGISTRY[frame_type.TYPE] = frame_type
