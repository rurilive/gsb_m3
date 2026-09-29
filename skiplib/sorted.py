"""朴素有序集合：内部只有一个保持有序的 list。

元素可比较，集合语义（重复 add 幂等）。定位与查找都是线性扫描，插入还要把
后半段整体搬移，元素规模化之后这三处开销都是瓶颈。这里没有多层索引、没有可
复现的层高，也没有能反映成本的访问计数，作为跳表改造前的基线实现。
"""


class FlatSorted:
    """有序集合的朴素基线，底层是一个升序 list。"""

    def __init__(self):
        self._items = []

    def add(self, x):
        """插入 x，集合语义：已存在则幂等，返回 False；否则插入返回 True。"""
        if x is None:
            raise TypeError("元素不能为 None")
        i = 0
        n = len(self._items)
        while i < n and self._items[i] < x:
            i += 1
        if i < n and self._items[i] == x:
            return False
        self._items.insert(i, x)
        return True

    def contains(self, x):
        """线性查找 x 是否存在。"""
        for item in self._items:
            if item == x:
                return True
        return False

    def discard(self, x):
        """删除一个 x，返回是否真的删掉了；不存在时返回 False。"""
        for i, item in enumerate(self._items):
            if item == x:
                del self._items[i]
                return True
        return False

    def rank(self, x):
        """返回严格小于 x 的元素个数。"""
        count = 0
        for item in self._items:
            if item < x:
                count += 1
        return count

    def kth(self, i):
        """返回第 i 小元素，下标从 0 起；越界抛 ValueError。"""
        if i < 0 or i >= len(self._items):
            raise ValueError("下标越界: %r" % (i,))
        return self._items[i]

    def range_query(self, lo, hi):
        """线性扫描返回闭区间 [lo, hi] 内的元素，按升序排列。"""
        out = []
        for item in self._items:
            if lo <= item <= hi:
                out.append(item)
        return out

    def __len__(self):
        return len(self._items)
