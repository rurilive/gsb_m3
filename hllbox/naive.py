"""hllbox 的现有实现。

这里只有一套朴素的全量精确去重：每见到一个元素就把它的字符串原样
记进一个集合，count 返回集合的大小也就是不同元素的个数。计数是精确
的，但集合会随不同元素的个数一直涨，元素基数大时内存无界；也拿不出
固定内存的估计与误差上界，不能把两个结构并起来算并集，没有被桶
分摊的概念，更没有稀疏与稠密两套表示。
"""


class ExactSet:
    """朴素的全量精确去重集合。

    只做一件确定的事：把每个见过的不同元素原样记住，count 给出不同
    元素的精确个数。所有元素一视同仁地被留在一个集合里，谁也不丢，
    所以元素种类越多占的内存越多。
    """

    def __init__(self):
        self._items = set()

    def add(self, key):
        """把一个元素记进集合。

        key 必须是非空字符串，否则抛 ValueError。重复加入同一元素
        不改变不同元素的个数。
        """
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty str")
        self._items.add(key)

    def add_many(self, keys):
        """批量加入一串元素，逐个走与 add 相同的校验。"""
        for key in keys:
            self.add(key)

    def count(self):
        """当前记住的不同元素的精确个数，空集合为零。"""
        return len(self._items)

    def contains(self, key):
        """元素是否已经被记进集合。"""
        return key in self._items

    def union(self, other):
        """把另一个集合的元素并进来，返回 self。

        只接受 ExactSet，否则抛 ValueError。并集是精确的。
        """
        if not isinstance(other, ExactSet):
            raise ValueError("other must be an ExactSet")
        self._items |= other._items
        return self

    def reset(self):
        """清空全部元素，回到刚建立时的状态。"""
        self._items = set()
