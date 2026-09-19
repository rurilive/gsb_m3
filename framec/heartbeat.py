"""心跳扩展帧：PING / PONG / VERSION。

导入本模块即把三种帧（0x10 / 0x11 / 0x20）注册进共享 REGISTRY，
编解码核心不用动。注册放在导入时而不是 framec/__init__.py，保证
test_framec.py 对注册表初始快照的锁定仍为绿色。

PING/PONG：8 字节大端 u64 单调时间戳（time.monotonic_ns()）；PONG 原样
回显 PING 时间戳，RTT = 回包时刻 - 时间戳。VERSION：非空 list[int]，载荷
为逗号分隔十进制 ASCII（如 b"1,3"）。长度/编码不合法抛 PayloadError。

int 值与 ACK 撞型，三种新帧编码时必须显式传 ftype，不进自动推断。
"""

import struct

from framec.errors import PayloadError
from framec.registry import FrameType, register


def _check_u64(value):
    if (not isinstance(value, int) or isinstance(value, bool)
            or not 0 <= value <= 0xFFFFFFFFFFFFFFFF):
        raise PayloadError("时间戳必须是 u64 非负整数: %r" % (value,))


class PingFrame(FrameType):
    """0x10 PING：8 字节大端 u64 单调时间戳（time.monotonic_ns）。"""

    TYPE = 0x10
    NAME = "PING"

    def encode(self, value):
        _check_u64(value)
        return struct.pack(">Q", value)

    def decode(self, payload):
        if len(payload) != 8:
            raise PayloadError("PING 载荷必须 8 字节，实际 %d" % len(payload))
        return struct.unpack(">Q", payload)[0]


class PongFrame(PingFrame):
    """0x11 PONG：原样回显 PING 的时间戳，用于 RTT 配对。"""

    TYPE = 0x11
    NAME = "PONG"

    def decode(self, payload):
        if len(payload) != 8:
            raise PayloadError("PONG 载荷必须 8 字节，实际 %d" % len(payload))
        return struct.unpack(">Q", payload)[0]


class VersionFrame(FrameType):
    """0x20 VERSION：非空 int 列表，载荷逗号分隔十进制 ASCII，如 b"1,3"。"""

    TYPE = 0x20
    NAME = "VERSION"

    def encode(self, value):
        if not isinstance(value, list) or not value:
            raise PayloadError("VERSION 值必须是非空 list[int]")
        parts = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                raise PayloadError("VERSION 元素必须是非负 int: %r" % (item,))
            parts.append(str(item))
        return b",".join(part.encode("ascii") for part in parts)

    def decode(self, payload):
        if not payload:
            raise PayloadError("VERSION 载荷为空")
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError as e:
            raise PayloadError("VERSION 载荷不是 ASCII: %s" % e)
        versions = []
        for token in text.split(","):
            if not token or not token.isdigit():
                raise PayloadError("VERSION 十进制版本号非法: %r" % token)
            versions.append(int(token))
        return versions


register(PingFrame())
register(PongFrame())
register(VersionFrame())
