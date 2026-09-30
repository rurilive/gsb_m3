"""splayx：纯标准库的有序多重集合。

当前只提供一个朴素实现：SortedBag 用一份始终保持升序的 list 存放元素，
插入与删除都要在数组中间搬动元素。包内不依赖任何第三方库。
"""

from .btree import SortedBag

__all__ = ["SortedBag"]
