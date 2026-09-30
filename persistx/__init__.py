"""persistx：序列版本化统计工具包（当前为改造前的朴素基线）。

导出 PersistSeq 类与全部异常类型。基线每个版本都整份复制数组，
历史全量留痕，查询直接在副本上切片。
"""

from .pst import (
    EmptySeqError,
    IndexRangeError,
    PersistSeq,
    PstError,
    VersionError,
)

__all__ = [
    "EmptySeqError",
    "IndexRangeError",
    "PersistSeq",
    "PstError",
    "VersionError",
]
