"""walog: 预写日志与掉电恢复。"""

from .store import KVStore
from .wal import WriteAheadLog

__all__ = ["KVStore", "WriteAheadLog"]
