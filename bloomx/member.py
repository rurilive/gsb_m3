"""bloomx 的成员集合实现。

当前是最朴素的实现：内部用 Python 的 set 精确保存每一个加入的元素，
查询时直接做集合成员判断，因此不存在误判，代价是内存随元素数量线性增长。
"""


class ExactSet:
    """精确成员集合。

    用 Python 内置 set 保存全部元素，add 与 contains 都是精确语义：
    加入过的元素一定判为存在，没加入过的元素一定判为不存在。
    """

    def __init__(self):
        self._members = set()

    def add(self, item):
        """加入一个元素。"""
        self._members.add(item)

    def contains(self, item):
        """判断元素是否存在，精确无误差。"""
        return item in self._members

    def size(self):
        """当前集合中的元素个数。"""
        return len(self._members)

    def __len__(self):
        return len(self._members)
