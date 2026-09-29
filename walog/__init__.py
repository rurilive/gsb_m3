"""walog：一个纯标准库的预写日志。

当前对外能力是 Log：一边往内存列表里追加负载，一边按位置读回，带一个长度
与清空。带序号的条目、检查点、截断与重放、崩溃恢复与校验和都留待在这个
基础上补齐。
"""

from .errors import CorruptEntry, InvalidLsn, TruncateError, WalogError
from .log import Log

__all__ = [
    "CorruptEntry",
    "InvalidLsn",
    "Log",
    "TruncateError",
    "WalogError",
]
