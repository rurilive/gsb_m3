"""心跳与版本协商扩展帧：PING / PONG / VERSION（类型码 0x10/0x11/0x20）。

按需扩展示例：显式 import 本模块即完成注册，编解码核心与 framec 包默认
注册表均不受影响。新帧值类型（int / list）会撞自动推断规则，编码时必须
显式传 ftype（实例 / 类 / 已注册类型码均可）。
"""

import struct

from framec.errors import PayloadError
from framec.registry import FrameType, register


class _TimestampFrame(FrameType):
    """8 字节大端 u64 单调时间戳（time.monotonic_ns），值类型 int。"""

    def encode(self, value):
        if (not isinstance(value, int) or isinstance(value, bool)
                or not 0 <= value <= 0xFFFFFFFFFFFFFFFF):
            raise PayloadError("%s 值必须是 u64 时间戳: %r" % (self.NAME, value))
        return struct.pack(">Q", value)

    def decode(self, payload):
        if len(payload) != 8:
            raise PayloadError(
                "%s 载荷必须 8 字节，实际 %d" % (self.NAME, len(payload)))
        return struct.unpack(">Q", payload)[0]


class PingFrame(_TimestampFrame):
    """0x10 PING：心跳探测，载荷为发送时刻的单调时间戳。"""

    TYPE = 0x10
    NAME = "PING"


class PongFrame(_TimestampFrame):
    """0x11 PONG：原样回显 PING 时间戳，RTT = 收包时刻 - 回显值。"""

    TYPE = 0x11
    NAME = "PONG"


class VersionFrame(FrameType):
    """0x20 VERSION：握手互报版本，值 list[int]，载荷逗号分隔十进制 ASCII。"""

    TYPE = 0x20
    NAME = "VERSION"

    def encode(self, value):
        if (not isinstance(value, list) or not value
                or any(not isinstance(v, int) or isinstance(v, bool) or v < 0
                       for v in value)):
            raise PayloadError("VERSION 值必须是非空 list[int]: %r" % (value,))
        return ",".join(str(v) for v in value).encode("ascii")

    def decode(self, payload):
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError as e:
            raise PayloadError("VERSION 载荷不是合法 ASCII: %s" % e)
        parts = text.split(",")
        if not all(part.isdigit() for part in parts):
            raise PayloadError("VERSION 载荷必须是逗号分隔十进制: %r" % (text,))
        return [int(part) for part in parts]


register(PingFrame())
register(PongFrame())
register(VersionFrame())
