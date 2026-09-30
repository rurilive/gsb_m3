"""splayx.btree：有序多重集合的朴素实现。

SortedBag 内部维持一个升序的 list；所有查询都在这份数组上完成，
插入与删除会用 list 的切片赋值在中间搬动元素，前驱后继与第 k 小
直接排序或线性扫描。行为简单、实现直白，但每次中间插入或删除的
代价随元素个数线性增长，也没有任何可供复用的树状层级。
"""

import bisect


class BagError(Exception):
    """本模块所有自定义异常的基类。"""


class SortedBag(object):
    """一个始终保持升序的有序多重集合。

    内部只有一个 list 作为存储，元素按非递减顺序排列，允许重复值。
    构造时可以传入任意可迭代对象作为初始元素。
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
        """删除一个等于 x 的元素；不存在时抛 BagError 立即失败。"""
        i = bisect.bisect_left(self._data, x)
        if i >= len(self._data) or self._data[i] != x:
            raise BagError("元素不存在: %r" % (x,))
        del self._data[i]

    def find(self, x):
        """x 存在时返回等价的一个元素，否则返回 None。"""
        i = bisect.bisect_left(self._data, x)
        if i < len(self._data) and self._data[i] == x:
            return self._data[i]
        return None

    def kth(self, i):
        """返回第 i 小（零基）的元素；越界抛 BagError。

        当前直接按下标取排序后的数组元素。
        """
        if i < 0 or i >= len(self._data):
            raise BagError("kth 越界: %r" % (i,))
        return self._data[i]

    def rank(self, x):
        """返回严格小于 x 的元素个数。"""
        return bisect.bisect_left(self._data, x)

    def predecessor(self, x):
        """返回严格小于 x 的最大元素；不存在返回 None。"""
        pos = bisect.bisect_left(self._data, x)
        if pos == 0:
            return None
        return self._data[pos - 1]

    def successor(self, x):
        """返回严格大于 x 的最小元素；不存在返回 None。"""
        pos = bisect.bisect_right(self._data, x)
        if pos >= len(self._data):
            return None
        return self._data[pos]

    def count_range(self, lo, hi):
        """返回落在闭区间 [lo, hi] 内的元素个数；lo > hi 时返回 0。"""
        if lo > hi:
            return 0
        return bisect.bisect_right(self._data, hi) - bisect.bisect_left(self._data, lo)

    def to_list(self):
        """返回当前所有元素的一份升序拷贝。"""
        return list(self._data)

    def inorder(self):
        """返回中序遍历结果，朴素实现下即升序数组的一份拷贝。"""
        return list(self._data)
