"""seal/unseal：把一份 bytes 装进容器，或者从容器里取回来。

顺序是固定死的：先按头部里记的密钥版本挑密钥，验标签，最后才解密。
标签对不上就抛 AuthError，一个明文字节都不往外吐。
"""

import os

from .format import NONCE_LEN, SALT_LEN, FormatError, pack_v1, parse_v1
from .keystream import derive, mac, normalize_key, verify_mac, xor_stream

ENC_LABEL = b"enc"
MAC_LABEL = b"mac"
NONCE_LABEL = b"nonce"
DEFAULT_KEY_VERSION = 1


class VaultError(Exception):
    """vaultfile 的公共错误基类。"""


class AuthError(VaultError):
    """容器结构坏了，或者认证标签对不上，反正没解出可信明文。"""


class UnknownKeyError(VaultError):
    """密钥环里找不到容器头部写的那个版本。"""


def select_key(keyring, version):
    """按版本取密钥。

    keyring 可以是 {版本: 密钥} 的映射，也可以是一把裸密钥（老用法，
    版本字段被忽略）。映射里没有这个版本就抛 UnknownKeyError。
    """
    if isinstance(keyring, dict):
        if version not in keyring:
            raise UnknownKeyError("no key for version %r" % (version,))
        return normalize_key(keyring[version])
    return normalize_key(keyring)


def _subkeys(key, salt):
    """一份文件两根子密钥：一根出密钥流，一根出标签。"""
    return derive(key, ENC_LABEL, salt), derive(key, MAC_LABEL, salt)


def seal(data, key, key_version=DEFAULT_KEY_VERSION):
    """整段加密，返回自包含的容器字节串。

    盐每次现取，所以同一份明文用同一把密钥加两次，出来的是两串字节。
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes, got %s" % (type(data).__name__,))
    selected = select_key(key, key_version)
    salt = os.urandom(SALT_LEN)
    enc_key, mac_key = _subkeys(selected, salt)
    nonce = derive(selected, NONCE_LABEL, salt)[:NONCE_LEN]
    header = pack_v1(key_version, salt, nonce, len(data))
    ciphertext = xor_stream(enc_key, nonce, data)
    tag = mac(mac_key, header + ciphertext)
    return header + ciphertext + tag


def unseal(blob, key):
    """整段解密。认不出容器、标签对不上，一律 AuthError。"""
    try:
        header, version, salt, nonce, ciphertext, tag = parse_v1(blob)
    except FormatError as exc:
        raise AuthError("container is malformed: %s" % (exc,)) from exc
    selected = select_key(key, version)
    _enc_key, mac_key = _subkeys(selected, salt)
    if not verify_mac(mac_key, header + ciphertext, tag):
        raise AuthError("tag mismatch, container was altered")
    enc_key = derive(selected, ENC_LABEL, salt)
    return xor_stream(enc_key, nonce, ciphertext)


def seal_file(path, data, key, key_version=DEFAULT_KEY_VERSION):
    """加密后写进文件，返回写出去的字节数。"""
    blob = seal(data, key, key_version)
    with open(path, "wb") as handle:
        handle.write(blob)
    return len(blob)


def unseal_file(path, key):
    """读文件解密。文件不存在让它抛 OSError，不吞。"""
    with open(path, "rb") as handle:
        blob = handle.read()
    return unseal(blob, key)


# v2 分块流式入口放在 chunked 模块；那里只在函数体内反向导入本模块，
# 所以这里模块级导入不会成环。
from .chunked import rotate_file, seal_stream, unseal_stream  # noqa: E402
