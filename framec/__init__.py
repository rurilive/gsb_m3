"""framec: 二进制帧编解码，注册表驱动 + CRC 校验管线。"""

from framec.codec import Decoder, Encoder, Frame
from framec.errors import (
    CrcError,
    FrameError,
    HeaderError,
    PayloadError,
    UnknownTypeError,
)
from framec.registry import REGISTRY, FrameType, register
from framec import types
from framec.types import AckFrame, DataFrame, JsonFrame

__all__ = [
    "Encoder", "Decoder", "Frame",
    "FrameError", "HeaderError", "CrcError", "UnknownTypeError", "PayloadError",
    "FrameType", "REGISTRY", "register",
    "DataFrame", "JsonFrame", "AckFrame",
]
