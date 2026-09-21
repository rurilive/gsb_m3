"""逻辑名字的校验与到磁盘路径的映射。

名字限 ASCII 字母数字与 . _ -，首字符必须是字母或数字，最长 64；
落盘时按前两个字符分片，避免单目录里堆上太多文件。
"""

import re

from blobvault.errors import InvalidKey

OBJECTS_DIR = "objects"
OBJECT_SUFFIX = ".blob"
SHARD_LEN = 2

KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_key(key):
    """校验逻辑名字，非法时抛 InvalidKey，合法时原样返回。"""
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise InvalidKey("非法名字: %r" % (key,))
    return key


def shard_of(key):
    """取名字所在的分片目录名，不足两位的下划线补齐。"""
    validate_key(key)
    return key[:SHARD_LEN].ljust(SHARD_LEN, "_")


def key_relpath(key):
    """返回名字对应的相对路径，形如 objects/ab/name.blob。"""
    validate_key(key)
    return "%s/%s/%s%s" % (OBJECTS_DIR, shard_of(key), key, OBJECT_SUFFIX)
