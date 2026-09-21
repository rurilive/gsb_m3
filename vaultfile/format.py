"""v1 容器结构：整份文件一套头，尾上一个认证标签。

布局：

    magic(4) | fmt(1) | key_version(1) | salt(16) | nonce(16) | length(8)
    | ciphertext(length) | tag(32)

length 写的是密文长度，必须和文件里实际带着的密文一样长。长度对不上说明
文件被截过或者被人补过。tag 盖住头部加全部密文，头部里有密钥版本，版本被
改过一样过不了认证。

这一层只管结构，不碰内容：tag 是不是有效由 vault 层拿密钥验。
"""

import struct

MAGIC_V1 = b"VLT1"
FMT_V1 = 1
SALT_LEN = 16
NONCE_LEN = 16
TAG_LEN = 32
_HEADER = struct.Struct(">4sBB16s16sQ")
HEADER_LEN = _HEADER.size


class FormatError(ValueError):
    """字节串不符合容器结构：magic 不对，太短，字段之间对不上。"""


def pack_v1(key_version, salt, nonce, length):
    """拼一个 46 字节的容器头部。"""
    if not isinstance(key_version, int) or isinstance(key_version, bool):
        raise FormatError("key version must be an int")
    if not 0 <= key_version <= 255:
        raise FormatError("key version out of range: %r" % (key_version,))
    if isinstance(salt, bytearray):
        salt = bytes(salt)
    if isinstance(nonce, bytearray):
        nonce = bytes(nonce)
    if not isinstance(salt, bytes) or len(salt) != SALT_LEN:
        raise FormatError("salt must be exactly %d bytes" % (SALT_LEN,))
    if not isinstance(nonce, bytes) or len(nonce) != NONCE_LEN:
        raise FormatError("nonce must be exactly %d bytes" % (NONCE_LEN,))
    if not isinstance(length, int) or isinstance(length, bool) or length < 0:
        raise FormatError("length must be a non-negative int")
    return _HEADER.pack(MAGIC_V1, FMT_V1, key_version, salt, nonce, length)


def parse_v1(blob):
    """拆开容器，返回 (header, key_version, salt, nonce, ciphertext, tag)。"""
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes):
        raise FormatError("container must be bytes, got %s" % (type(blob).__name__,))
    if len(blob) < HEADER_LEN + TAG_LEN:
        raise FormatError(
            "container shorter than the smallest possible one: %d" % (len(blob),)
        )
    magic, fmt, key_version, salt, nonce, length = _HEADER.unpack_from(blob, 0)
    if magic != MAGIC_V1:
        raise FormatError("bad magic %r" % (magic,))
    if fmt != FMT_V1:
        raise FormatError("unsupported format version %d" % (fmt,))
    carried = len(blob) - HEADER_LEN - TAG_LEN
    if length != carried:
        raise FormatError(
            "length field says %d bytes of ciphertext, file carries %d"
            % (length, carried)
        )
    header = blob[:HEADER_LEN]
    ciphertext = blob[HEADER_LEN : HEADER_LEN + length]
    tag = blob[-TAG_LEN:]
    return header, key_version, salt, nonce, ciphertext, tag


def looks_v1(blob):
    """只看前四个字节，给读入口分流用。"""
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes):
        raise FormatError("container must be bytes, got %s" % (type(blob).__name__,))
    return blob[:4] == MAGIC_V1


# ---------------------------------------------------------------------------
# v2：定长分块的流式容器
#
# 文件头只有一份：
#
#     magic(4) | fmt(1) | key_version(1) | salt(16) | chunk_size(4)
#
# key_version 是封装时用的默认版本，仅作信息记录；解密时密钥版本以每块
# 自己块头里记的为准，这样 rotate_file 之后新旧版本可以混排。salt 是这份
# 文件独有的随机量，参与每块 nonce 派生，跨文件不重样。chunk_size 是非
# 末块的明文/密文定长。
#
# 后面跟着一串块帧，每帧：
#
#     chunk_header(10) | ciphertext(length) | tag(32)
#
# 块头 = index(4, 大端) | flags(1) | length(4, 大端) | key_version(1)
# flags 的 bit0 标记末块；length 是本块密文长度；index 从 0 起逐块加一。
# tag 盖住 文件头 + 块头 + 本块密文，块号、版本、长度全在认证范围内，
# 调包、挪位、跨文件拼接都过不了认证。空文件也有一帧（length=0 的末块），
# 所以尾巴被整帧截掉时一定能发现。

MAGIC_V2 = b"VLT2"
FMT_V2 = 2
FLAG_FINAL = 0x01
V2_HEADER = struct.Struct(">4sBB16sI")
V2_HEADER_LEN = V2_HEADER.size
CHUNK_HEADER = struct.Struct(">IBIB")
CHUNK_HEADER_LEN = CHUNK_HEADER.size


def pack_v2_file_header(key_version, salt, chunk_size):
    """拼 v2 文件头。"""
    if not isinstance(key_version, int) or isinstance(key_version, bool):
        raise FormatError("key version must be an int")
    if not 0 <= key_version <= 255:
        raise FormatError("key version out of range: %r" % (key_version,))
    if isinstance(salt, bytearray):
        salt = bytes(salt)
    if not isinstance(salt, bytes) or len(salt) != SALT_LEN:
        raise FormatError("salt must be exactly %d bytes" % (SALT_LEN,))
    if (
        not isinstance(chunk_size, int)
        or isinstance(chunk_size, bool)
        or not 1 <= chunk_size <= 0xFFFFFFFF
    ):
        raise FormatError("chunk_size must be an int in [1, 2^32-1]")
    return V2_HEADER.pack(MAGIC_V2, FMT_V2, key_version, salt, chunk_size)


def parse_v2_file_header(blob):
    """拆 v2 文件头，返回 (header, key_version, salt, chunk_size)。"""
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes) or len(blob) < V2_HEADER_LEN:
        raise FormatError("v2 file header too short")
    magic, fmt, key_version, salt, chunk_size = V2_HEADER.unpack_from(blob, 0)
    if magic != MAGIC_V2:
        raise FormatError("bad magic %r" % (magic,))
    if fmt != FMT_V2:
        raise FormatError("unsupported format version %d" % (fmt,))
    return bytes(blob[:V2_HEADER_LEN]), key_version, salt, chunk_size


def pack_v2_chunk_header(index, flags, length, key_version):
    """拼一个块头。"""
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index <= 0xFFFFFFFF:
        raise FormatError("chunk index out of range: %r" % (index,))
    if not isinstance(flags, int) or isinstance(flags, bool) or not 0 <= flags <= 0xFF:
        raise FormatError("flags out of range: %r" % (flags,))
    if flags & ~FLAG_FINAL:
        raise FormatError("unknown chunk flags: 0x%02x" % (flags,))
    if not isinstance(length, int) or isinstance(length, bool) or not 0 <= length <= 0xFFFFFFFF:
        raise FormatError("chunk length out of range: %r" % (length,))
    if not isinstance(key_version, int) or isinstance(key_version, bool):
        raise FormatError("key version must be an int")
    if not 0 <= key_version <= 255:
        raise FormatError("key version out of range: %r" % (key_version,))
    return CHUNK_HEADER.pack(index, flags, length, key_version)


def parse_v2_chunk_header(blob):
    """拆一个块头，返回 (header, index, flags, length, key_version)。"""
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes) or len(blob) < CHUNK_HEADER_LEN:
        raise FormatError("chunk header too short")
    index, flags, length, key_version = CHUNK_HEADER.unpack_from(blob, 0)
    if flags & ~FLAG_FINAL:
        raise FormatError("unknown chunk flags: 0x%02x" % (flags,))
    return bytes(blob[:CHUNK_HEADER_LEN]), index, flags, length, key_version


def looks_v2(blob):
    """只看前四个字节，给读入口分流用。"""
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes):
        raise FormatError("container must be bytes, got %s" % (type(blob).__name__,))
    return blob[:4] == MAGIC_V2
