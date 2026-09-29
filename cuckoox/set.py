"""cuckoox 的基线实现：精确成员集合 ExactBag。

这一版就是最朴素的做法，内部只有一个 Python 集合，
没有哈希表、没有位数组、也没有误判这个概念：

- add(item)     把元素放进集合，重复加入不改变大小
- discard(item) 删除元素，元素不在集合里也不报错
- contains(item) 精确判断元素是否在集合里，零误差
- size()        当前元素个数；len(bag) 等价

因为底层是 Python 集合，精确是精确，代价是内存随元素数量线性增长，
既不能压缩，也不能用一点点误判率去换内存。
"""


class ExactBag:
    """精确成员集合，内部就是一个 Python 集合。"""

    def __init__(self):
        self._items = set()

    def add(self, item):
        """加入一个元素；重复加入幂等。"""
        self._items.add(item)

    def discard(self, item):
        """删除一个元素；元素不在集合里时静默返回，不报错。"""
        self._items.discard(item)

    def contains(self, item):
        """精确判断元素是否在集合里，零假阴性与零假阳性。"""
        return item in self._items

    def size(self):
        """当前元素个数。"""
        return len(self._items)

    def __len__(self):
        return len(self._items)

    def __contains__(self, item):
        return self.contains(item)

    def __repr__(self):
        return "ExactBag(size={0})".format(len(self._items))
