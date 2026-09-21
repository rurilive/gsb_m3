"""线格式的紧凑原语。

格式是 CBOR 风格的规范形：每个值以一个首部字节开头，高三位是主类型，
低五位是附加信息。附加信息 0..23 直接携带参数；24/25/26/27 表示后跟
1/2/4/8 字节大端参数，且必须取能放下的最小宽度（最短形）。浮点用三个
固定类型码：TAG_FLOAT16 半精度、TAG_FLOAT32 单精度、TAG_FLOAT64 双精度，
编码时取能无损表示的最短宽度，NaN 固定为 d97e00。

主类型：0 非负整数，1 负整数（参数为 -1-n），2 字节串，3 文本（UTF-8，
参数是字节长度），4 数组，5 字段表（键必须是文本，按规范序排列）。
嵌套深度上限 MAX_DEPTH，编解码两侧都生效。

偏移约定：输入提前耗尽时 DecodeError.offset 取输入长度，也就是下一个
本该出现却没有的字节。
"""

import math
import struct

from packwire.errors import DecodeError, EncodeError

MAJOR_UINT = 0
MAJOR_NEGINT = 1
MAJOR_BYTES = 2
MAJOR_TEXT = 3
MAJOR_ARRAY = 4
MAJOR_MAP = 5

TAG_FLOAT16 = 0xD9
TAG_FLOAT32 = 0xDA
TAG_FLOAT64 = 0xDB

FLOAT_TAGS = frozenset([TAG_FLOAT16, TAG_FLOAT32, TAG_FLOAT64])
FLOAT_TYPES = (
    (TAG_FLOAT16, ">e", 2),
    (TAG_FLOAT32, ">f", 4),
    (TAG_FLOAT64, ">d", 8),
)

INT_MIN = -(1 << 64)
INT_MAX = (1 << 64) - 1

MAX_DEPTH = 100

# 附加信息 -> (参数字节数, struct 格式, 该宽度允许的最小参数)
LONG_INFO = {
    24: (1, ">B", 24),
    25: (2, ">H", 1 << 8),
    26: (4, ">I", 1 << 16),
    27: (8, ">Q", 1 << 32),
}


def pack_head(major, argument):
    """主类型 + 参数的最短形首部。"""
    if argument < 0:
        raise EncodeError("negative head argument: %d" % argument)
    if argument < 24:
        return bytes([(major << 5) | argument])
    if argument <= 0xFF:
        return bytes([(major << 5) | 24, argument])
    if argument <= 0xFFFF:
        return bytes([(major << 5) | 25]) + struct.pack(">H", argument)
    if argument <= 0xFFFFFFFF:
        return bytes([(major << 5) | 26]) + struct.pack(">I", argument)
    if argument <= 0xFFFFFFFFFFFFFFFF:
        return bytes([(major << 5) | 27]) + struct.pack(">Q", argument)
    raise EncodeError("head argument out of range: %d" % argument)


def pack_int(value):
    """整数的最短形编码，范围 -2^64 .. 2^64-1。"""
    if not INT_MIN <= value <= INT_MAX:
        raise EncodeError("integer out of range: %d" % value)
    if value >= 0:
        return pack_head(MAJOR_UINT, value)
    return pack_head(MAJOR_NEGINT, -1 - value)


def pack_float(value):
    """浮点的最短无损宽度编码，NaN 固定为 d97e00。"""
    if math.isnan(value):
        return bytes([TAG_FLOAT16]) + b"\x7e\x00"
    for tag, fmt, _size in FLOAT_TYPES[:2]:
        try:
            packed = struct.pack(fmt, value)
        except OverflowError:
            continue
        if struct.unpack(fmt, packed)[0] == value:
            return bytes([tag]) + packed
    return bytes([TAG_FLOAT64]) + struct.pack(">d", value)


def require(data, pos, n):
    """确认 data 从 pos 起还有 n 字节，不够按截断报错，返回新位置。"""
    if len(data) - pos < n:
        raise DecodeError("truncated input", len(data))
    return pos + n


def read_head(data, pos):
    """读首部，返回 (主类型, 参数, 新位置)；非最短形与保留附加信息报错。"""
    require(data, pos, 1)
    initial = data[pos]
    info = initial & 0x1F
    if info < 24:
        return initial >> 5, info, pos + 1
    size_info = LONG_INFO.get(info)
    if size_info is None:
        raise DecodeError("unsupported additional info: %d" % info, pos)
    size, fmt, minimum = size_info
    end = require(data, pos + 1, size)
    argument = struct.unpack_from(fmt, data, pos + 1)[0]
    if argument < minimum:
        raise DecodeError("non-canonical head: not shortest form", pos)
    return initial >> 5, argument, end
