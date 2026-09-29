"""bitlib 的基线实现：布尔列表存位的位集合。

BoolBits 把每一位存成一个布尔值，按位长铺成一个列表。置位与清零就是改
列表里的某一格，两个集合求与或需要逐位循环，没有字级存储、没有位运算。
"""


class BitlibError(Exception):
    """bitlib 自有异常基类。"""


class BoolBits(object):
    """用布尔列表存位的位集合，基线实现。"""

    def __init__(self, length):
        if not isinstance(length, int) or isinstance(length, bool):
            raise BitlibError("位长必须是整数")
        if length < 0:
            raise BitlibError("位长不能为负")
        self.length = length
        self._bits = [False] * length

    def set(self, i):
        self._check(i)
        self._bits[i] = True

    def clear(self, i):
        self._check(i)
        self._bits[i] = False

    def get(self, i):
        self._check(i)
        return self._bits[i]

    def count(self):
        total = 0
        for b in self._bits:
            if b:
                total += 1
        return total

    def union(self, other):
        self._check_pair(other)
        out = BoolBits(self.length)
        for i in range(self.length):
            out._bits[i] = self._bits[i] or other._bits[i]
        return out

    def intersection(self, other):
        self._check_pair(other)
        out = BoolBits(self.length)
        for i in range(self.length):
            out._bits[i] = self._bits[i] and other._bits[i]
        return out

    def to_list(self):
        return [i for i in range(self.length) if self._bits[i]]

    def _check(self, i):
        if not isinstance(i, int) or isinstance(i, bool):
            raise BitlibError("下标必须是整数")
        if i < 0 or i >= self.length:
            raise BitlibError("下标越界")

    def _check_pair(self, other):
        if not isinstance(other, BoolBits):
            raise BitlibError("只能与同类位集合运算")
        if other.length != self.length:
            raise BitlibError("两个位集合位长必须一致")

    def __len__(self):
        return self.length

    def __eq__(self, other):
        if not isinstance(other, BoolBits):
            return NotImplemented
        return self.length == other.length and self._bits == other._bits

    def __repr__(self):
        return "BoolBits(length=%d, set=%r)" % (self.length, self.to_list())
