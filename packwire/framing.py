"""线格式的定长原语。

当前格式里每个值以单字节类型码开头，载荷定长：

- TAG_INT：后跟 INT_SIZE 字节大端补码整数
- TAG_TEXT：后跟 COUNT_SIZE 字节大端字节长度，再跟 UTF-8 字节
- TAG_ARRAY：后跟 COUNT_SIZE 字节大端元素个数，再跟逐个元素的编码

偏移约定：输入提前耗尽时 DecodeError.offset 取输入长度，也就是下一个
本该出现却没有的字节。
"""

import struct

from packwire.errors import DecodeError, EncodeError

TAG_INT = 0
TAG_TEXT = 1
TAG_ARRAY = 2

INT_SIZE = 8
COUNT_SIZE = 4

INT_MIN = -(1 << 63)
INT_MAX = (1 << 63) - 1
COUNT_MAX = (1 << 32) - 1


def pack_tag(tag):
    """单字节类型码。"""
    if not 0 <= tag <= 0xFF:
        raise EncodeError("type code out of range: %d" % tag)
    return bytes([tag])


def pack_int(value):
    """八字节大端补码。"""
    if not INT_MIN <= value <= INT_MAX:
        raise EncodeError("integer out of range: %d" % value)
    return struct.pack(">q", value)


def pack_count(n):
    """四字节大端无符号长度头。"""
    if not 0 <= n <= COUNT_MAX:
        raise EncodeError("length out of range: %d" % n)
    return struct.pack(">I", n)


def require(data, pos, n):
    """确认 data 从 pos 起还有 n 字节，不够按截断报错，返回新位置。"""
    if len(data) - pos < n:
        raise DecodeError("truncated input", len(data))
    return pos + n


def read_tag(data, pos):
    """读单字节类型码，返回 (tag, 新位置)。"""
    require(data, pos, 1)
    return data[pos], pos + 1


def read_int(data, pos):
    """读八字节大端补码，返回 (值, 新位置)。"""
    end = require(data, pos, INT_SIZE)
    return struct.unpack_from(">q", data, pos)[0], end


def read_count(data, pos):
    """读四字节大端长度头，返回 (计数, 新位置)。"""
    end = require(data, pos, COUNT_SIZE)
    return struct.unpack_from(">I", data, pos)[0], end
