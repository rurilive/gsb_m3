"""内置帧类型：DATA / JSON / ACK，占用类型码 0x01-0x03。"""

import json as _json
import struct

from framec.errors import PayloadError
from framec.registry import FrameType, register


class DataFrame(FrameType):
    """0x01 DATA：UTF-8 文本载荷，值类型 str。"""

    TYPE = 0x01
    NAME = "DATA"

    def encode(self, value):
        if not isinstance(value, str):
            raise PayloadError("DATA 值必须是 str: %r" % type(value).__name__)
        return value.encode("utf-8")

    def decode(self, payload):
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as e:
            raise PayloadError("DATA 载荷不是合法 UTF-8: %s" % e)


class JsonFrame(FrameType):
    """0x02 JSON：单行 JSON 载荷，值类型 dict。"""

    TYPE = 0x02
    NAME = "JSON"

    def encode(self, value):
        try:
            text = _json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as e:
            raise PayloadError("JSON 序列化失败: %s" % e)
        return text.encode("utf-8")

    def decode(self, payload):
        try:
            return _json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise PayloadError("JSON 载荷解析失败: %s" % e)


class AckFrame(FrameType):
    """0x03 ACK：4 字节大端 u32 回执，值类型 int。"""

    TYPE = 0x03
    NAME = "ACK"

    def encode(self, value):
        if (not isinstance(value, int) or isinstance(value, bool)
                or not 0 <= value <= 0xFFFFFFFF):
            raise PayloadError("ACK 值必须是 u32 序号: %r" % (value,))
        return struct.pack(">I", value)

    def decode(self, payload):
        if len(payload) != 4:
            raise PayloadError("ACK 载荷必须 4 字节，实际 %d" % len(payload))
        return struct.unpack(">I", payload)[0]


register(DataFrame())
register(JsonFrame())
register(AckFrame())
