"""vaultfile：本地加密文件格式，纯标准库，无外部依赖。"""

from .format import FMT_V1, HEADER_LEN, MAGIC_V1, FormatError
from .keystream import BadKeyError, derive, keystream, mac, xor_stream
from .vault import (
    DEFAULT_KEY_VERSION,
    AuthError,
    UnknownKeyError,
    VaultError,
    seal,
    seal_file,
    unseal,
    unseal_file,
)

__all__ = [
    "AuthError",
    "BadKeyError",
    "DEFAULT_KEY_VERSION",
    "FMT_V1",
    "FormatError",
    "HEADER_LEN",
    "MAGIC_V1",
    "UnknownKeyError",
    "VaultError",
    "derive",
    "keystream",
    "mac",
    "seal",
    "seal_file",
    "unseal",
    "unseal_file",
    "xor_stream",
]
