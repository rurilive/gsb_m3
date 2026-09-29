"""syndigest：纯标准库的数据对账小包。

当前只提供最朴素的一层：FullSync 把本地整张数据表原样发给对端，对端
整体覆盖自己的表。没有摘要、没有差集、没有版本，也没有冲突合并。
"""

from .sync import FullSync

__all__ = ["FullSync"]
