"""基于 HMAC-SHA256 的密钥派生与伪随机流，只用标准库。

加密和解密共用 xor_stream：同一对 (key, nonce) 下同一条数据流异或两次
就回到原文。换 nonce 就是换流，nonce 重样等于把密钥流拿去复用。
"""

import hashlib
import hmac
import os

DIGEST_LEN = hashlib.sha256().digest_size
MIN_KEY_LEN = 16
MAX_KEY_LEN = 64
_COUNTER_BYTES = 8


class BadKeyError(ValueError):
    """密钥不是 bytes，或者长度不在允许区间。"""


def normalize_key(key):
    """收敛密钥类型：bytes 直接过，bytearray 拷成 bytes，其余拒绝。

    长度卡在 16 到 64 字节。太短的密钥在派生阶段就拦下来，别等出事。
    """
    if isinstance(key, bytearray):
        key = bytes(key)
    if not isinstance(key, bytes):
        raise BadKeyError("key must be bytes, got %s" % (type(key).__name__,))
    if not MIN_KEY_LEN <= len(key) <= MAX_KEY_LEN:
        raise BadKeyError(
            "key length %d out of [%d, %d]" % (len(key), MIN_KEY_LEN, MAX_KEY_LEN)
        )
    return key


def derive(key, label, info=b""):
    """从主密钥派生 32 字节子密钥。

    label 标用途，info 放上下文（盐、随机量之类）。两个用途必须用不同
    label，否则密钥流和认证标签会落在同一串字节上。
    """
    key = normalize_key(key)
    if isinstance(label, str):
        label = label.encode("ascii")
    if not isinstance(label, bytes) or not label:
        raise BadKeyError("label must be non-empty bytes")
    if isinstance(info, bytearray):
        info = bytes(info)
    if not isinstance(info, bytes):
        raise BadKeyError("info must be bytes")
    message = b"vaultfile/" + label + b"\x00" + info
    return hmac.new(key, message, hashlib.sha256).digest()


def keystream(key, nonce, length):
    """产出 length 字节伪随机流。

    每个 32 字节分组是 HMAC(key, nonce 后接 8 字节大端计数器)，计数器从 0
    起。同一对 (key, nonce) 调两次结果必须逐字节一样。
    """
    key = normalize_key(key)
    if isinstance(nonce, bytearray):
        nonce = bytes(nonce)
    if not isinstance(nonce, bytes) or not nonce:
        raise BadKeyError("nonce must be non-empty bytes")
    if not isinstance(length, int) or isinstance(length, bool):
        raise TypeError("length must be an int")
    if length < 0:
        raise ValueError("length must be >= 0")
    if length == 0:
        return b""
    base = hmac.new(key, nonce, hashlib.sha256)
    out = bytearray()
    counter = 0
    while len(out) < length:
        digest = base.copy()
        digest.update(counter.to_bytes(_COUNTER_BYTES, "big"))
        out.extend(digest.digest())
        counter += 1
    del out[length:]
    return bytes(out)


def xor_stream(key, nonce, data):
    """data 与密钥流逐字节异或，加解密是同一个函数。"""
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes, got %s" % (type(data).__name__,))
    if not data:
        return b""
    stream = keystream(key, nonce, len(data))
    mixed = int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")
    return mixed.to_bytes(len(data), "big")


def mac(key, message):
    """认证标签，HMAC-SHA256，恒为 32 字节。"""
    key = normalize_key(key)
    if isinstance(message, bytearray):
        message = bytes(message)
    if not isinstance(message, bytes):
        raise TypeError("message must be bytes, got %s" % (type(message).__name__,))
    return hmac.new(key, message, hashlib.sha256).digest()


def verify_mac(key, message, tag):
    """恒时比较标签。长度不对直接 False。"""
    expected = mac(key, message)
    if isinstance(tag, bytearray):
        tag = bytes(tag)
    if not isinstance(tag, bytes) or len(tag) != len(expected):
        return False
    return hmac.compare_digest(expected, tag)


def random_nonce(length=16):
    """os.urandom 取一段随机量，做每份文件独立的盐或前缀。"""
    if not isinstance(length, int) or length <= 0:
        raise ValueError("length must be a positive int")
    return os.urandom(length)
