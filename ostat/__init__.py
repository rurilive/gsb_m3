"""ostat：纯标准库的有序统计结构。

当前只提供一个朴素实现：SortList 用一个始终保持升序的 list 存放元素，
插入与删除都需要在数组中间搬动元素。包内不依赖任何第三方库。
"""

from .stat import SortList

__all__ = ["SortList"]
