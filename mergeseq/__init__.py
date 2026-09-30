"""mergeseq：序列区间统计工具包的朴素基线。

导出 MergeSeq 类与全部异常类型。基线任何查询都在原序列上从头扫过
目标区间的每一个位置逐步累加或比较，查询之间零复用，规模一大就慢。
"""

from .mergeable import (
    EmptySeqError,
    IndexRangeError,
    MergeSeq,
    MergeableSegError,
    VersionError,
)

__all__ = [
    "EmptySeqError",
    "IndexRangeError",
    "MergeSeq",
    "MergeableSegError",
    "VersionError",
]
