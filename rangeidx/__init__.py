"""rangeidx: 内存表的二级有序索引。

当前只提供一份基于线性扫描的 Table，作为二级索引改造前的基线。
"""

from rangeidx.table import Table

__all__ = ["Table"]
