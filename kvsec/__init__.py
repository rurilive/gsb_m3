"""本地键值存储与字段二级索引，纯标准库。"""

from .index import SecondaryIndex
from .store import KVStore

__all__ = ["KVStore", "SecondaryIndex"]
