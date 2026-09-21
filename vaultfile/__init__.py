"""vaultfile：本地加密文件格式，纯标准库，无外部依赖。"""

from .chunked import (
    DEFAULT_CHUNK_SIZE,
    MAGIC_V2,
    rotate_file,
    seal_stream,
    unseal_stream,
)
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
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_KEY_VERSION",
    "FMT_V1",
    "FormatError",
    "HEADER_LEN",
    "MAGIC_V2",
    "MAGIC_V1",
    "UnknownKeyError",
    "VaultError",
    "derive",
    "keystream",
    "mac",
    "rotate_file",
    "seal",
    "seal_file",
    "seal_stream",
    "unseal",
    "unseal_file",
    "unseal_stream",
    "xor_stream",
]
