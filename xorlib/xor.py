"""朴素异或集合: 一切查询都在一个整数列表上从头到尾线性扫描。"""


class FlatXor:
    """用一个整数列表保存元素, 每次查询都扫全表。

    - add: 把元素追加进列表。
    - max_xor / min_xor: 线性找与给定值异或最大 / 最小的已有元素。
    - count_le: 线性统计不大于给定值的元素个数。
    - max_xor_pair: 枚举全部元素对求两两异或最大, 平方级。
    """

    def __init__(self):
        self._items = []

    def __len__(self):
        return len(self._items)

    def __contains__(self, x):
        return x in self._items

    def add(self, x):
        """加入元素 x。"""
        if not isinstance(x, int) or isinstance(x, bool):
            raise ValueError("element must be int")
        self._items.append(x)

    def values(self):
        """返回当前元素列表的一份拷贝。"""
        return list(self._items)

    def max_xor(self, x):
        """返回列表中与 x 异或最大的已有元素; 空集时抛 ValueError。"""
        if not self._items:
            raise ValueError("empty collection")
        best = None
        best_val = None
        for v in self._items:
            cur = v ^ x
            if best is None or cur > best_val:
                best = v
                best_val = cur
        return best

    def min_xor(self, x):
        """返回列表中与 x 异或最小的已有元素; 空集时抛 ValueError。"""
        if not self._items:
            raise ValueError("empty collection")
        best = None
        best_val = None
        for v in self._items:
            cur = v ^ x
            if best is None or cur < best_val:
                best = v
                best_val = cur
        return best

    def count_le(self, x):
        """返回列表中不大于 x 的元素个数 (线性扫描)。"""
        n = 0
        for v in self._items:
            if v <= x:
                n += 1
        return n

    def max_xor_pair(self):
        """枚举全部元素对, 返回两两异或最大值; 元素少于两个时抛 ValueError。"""
        if len(self._items) < 2:
            raise ValueError("need at least two elements")
        best = None
        for i in range(len(self._items)):
            for j in range(i + 1, len(self._items)):
                cur = self._items[i] ^ self._items[j]
                if best is None or cur > best:
                    best = cur
        return best
