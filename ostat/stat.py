"""ostat.stat：有序统计结构的朴素实现。

SortList 内部维持一个升序的 list；所有查询都在这个数组上完成，
插入与删除会用 list 的切片赋值在中间搬动元素。行为简单、
实现直白，但每次中间插入或删除的代价随元素个数线性增长。
"""

import bisect


class StatError(Exception):
    """本模块所有自定义异常的基类。"""


class SortList(object):
    """一个始终保持升序的有序列表。

    内部只有一个 list 作为存储，元素按非递减顺序排列。构造时可以
    传入任意可迭代对象作为初始元素。
    """

    def __init__(self, items=None):
        if items is None:
            items = []
        self._data = sorted(items)

    def __len__(self):
        return len(self._data)

    def __contains__(self, x):
        i = bisect.bisect_left(self._data, x)
        return i < len(self._data) and self._data[i] == x

    def insert(self, x):
        """二分找到插入位置，把 x 放进数组并保持升序。"""
        pos = bisect.bisect_left(self._data, x)
        self._data.insert(pos, x)

    def remove(self, x):
        """删除一个等于 x 的元素；不存在时抛 KeyError。"""
        i = bisect.bisect_left(self._data, x)
        if i >= len(self._data) or self._data[i] != x:
            raise KeyError(x)
        del self._data[i]

    def kth(self, i):
        """返回第 i 小（零基）的元素；越界抛 StatError。"""
        if i < 0 or i >= len(self._data):
            raise StatError("kth 越界: %r" % (i,))
        return self._data[i]

    def rank(self, x):
        """返回严格小于 x 的元素个数。"""
        return bisect.bisect_left(self._data, x)

    def count_range(self, l, r):
        """返回落在闭区间 [l, r] 内的元素个数；l > r 时返回 0。"""
        if l > r:
            return 0
        return bisect.bisect_right(self._data, r) - bisect.bisect_left(self._data, l)

    def to_list(self):
        """返回当前所有元素的一份升序拷贝。"""
        return list(self._data)
