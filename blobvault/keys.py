"""逻辑名字的校验、内容摘要与盘上路径映射。

盘上分三区：
- objects/<摘要前2位>/<64位摘要>   内容寻址的对象，同样字节只有一份；
- index/<名字前2位>/<名字>.ref     名字对对象摘要的引用；
- gc/pending                        回收失败的欠账本，下次 gc 重试。
名字限 ASCII 字母数字与 . _ -，首字符必须是字母或数字，最长 64。
所有写入先走同目录临时文件再原子改名，半成品临时文件统一 .bvtmp 后缀。
"""

import hashlib
import re

from blobvault.errors import InvalidKey

OBJECTS_DIR = "objects"
INDEX_DIR = "index"
GC_DIR = "gc"
REF_SUFFIX = ".ref"
TMP_SUFFIX = ".bvtmp"
LEDGER_NAME = "pending"
SHARD_LEN = 2
DIGEST_LEN = 64

KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{%d}$" % DIGEST_LEN)


def validate_key(key):
    """校验逻辑名字，非法时抛 InvalidKey，合法时原样返回。"""
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise InvalidKey("非法名字: %r" % (key,))
    return key


def shard_of(key):
    """取名字所在的分片目录名，不足两位的下划线补齐。"""
    validate_key(key)
    return key[:SHARD_LEN].ljust(SHARD_LEN, "_")


def digest_of(data):
    """返回 data 的 sha256 十六进制摘要（64 字符）。"""
    return hashlib.sha256(data).hexdigest()


def is_digest(text):
    """text 是否是合法的 64 位十六进制内容摘要。"""
    return isinstance(text, str) and bool(DIGEST_RE.match(text))


def parse_digest(text):
    """把十六进制摘要转成规范化形式，非法时抛 binascii.Error/ValueError。"""
    if not is_digest(text):
        raise ValueError("非法内容摘要: %r" % (text,))
    return text.lower()


def object_relpath(digest):
    """返回摘要对象的相对路径，形如 objects/ab/<64位摘要>。"""
    digest = parse_digest(digest)
    return "%s/%s/%s" % (OBJECTS_DIR, digest[:SHARD_LEN], digest)


def ref_relpath(key):
    """返回名字引用的相对路径，形如 index/ab/name.ref。"""
    validate_key(key)
    return "%s/%s/%s%s" % (INDEX_DIR, shard_of(key), key, REF_SUFFIX)


def ledger_relpath():
    """返回回收欠账本的相对路径。"""
    return "%s/%s" % (GC_DIR, LEDGER_NAME)


def tmp_relpath(final_relpath, nonce):
    """给目标相对路径生成同目录下的临时文件相对路径。"""
    parent, _, leaf = final_relpath.rpartition("/")
    tmp_leaf = ".%s.%s%s" % (leaf, nonce, TMP_SUFFIX)
    return "%s/%s" % (parent, tmp_leaf) if parent else tmp_leaf
