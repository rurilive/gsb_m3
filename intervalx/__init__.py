"""intervalx: 区间集合工具。

当前只提供基于线性扫描的 FlatIntervals，作为区间索引改造前的基线。
"""

from intervalx.tree import FlatIntervals, IntervalError, InvalidInterval

__all__ = ["FlatIntervals", "IntervalError", "InvalidInterval"]
