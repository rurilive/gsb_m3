"""skiplib: 纯标准库的有序集合工具。

当前只提供基于有序 list 的朴素基线 FlatSorted，作为跳表改造前的有序集合。
"""

from skiplib.sorted import FlatSorted

__all__ = ["FlatSorted"]
