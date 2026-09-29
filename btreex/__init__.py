"""btreex: 有序映射。

当前只提供基于平铺有序数组的 FlatMap，作为 B 树改造前的有序映射基线。
"""

from btreex.store import FlatMap

__all__ = ["FlatMap"]
