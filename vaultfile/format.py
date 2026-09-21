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
