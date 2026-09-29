"""BruteQueries: 朴素离线区间查询（改造前基线）。

内部只有一个数组，所有区间统计都是每个查询各自独立地把区间扫一遍：

- distinct(l, r)：逐项统计半开区间 [l, r) 内不同值的个数
- mode_count(l, r)：逐项统计区间内出现次数最多的值的出现次数
- sum_of_squares(l, r)：逐项统计区间内各值出现次数的平方和

区间一律是左闭右开的半开区间 [l, r)，元素下标从 0 数起。每个查询
都从头把区间重新扫一遍，查询一多、区间一长就白扫，没有任何复用。
"""


class MoError(Exception):
    """molib 里所有可预期错误的基类。"""


class BadRange(MoError):
    """区间下标越界或左右端点次序颠倒。"""


class BruteQueries:
    """朴素离线区间查询：每次查询都独立重扫区间。"""

    def __init__(self, data):
        """用序列 data 建实例，内部存一份数组副本。"""
        self._data = list(data)

    # -- 只读视图 ---------------------------------------------------------

    @property
    def data(self):
        """返回内部数组的副本。"""
        return list(self._data)

    def size(self):
        """数组长度。"""
        return len(self._data)

    # -- 内部校验 ---------------------------------------------------------

    def _check(self, l, r):
        """检查半开区间 [l, r) 是否合法，非法就地快速失败。"""
        n = len(self._data)
        if not isinstance(l, int) or not isinstance(r, int):
            raise BadRange("区间端点必须是整数: %r %r" % (l, r))
        if not (0 <= l <= r <= n):
            raise BadRange("区间越界或次序颠倒: [%r, %r)" % (l, r))
        return l, r

    # -- 朴素查询 ---------------------------------------------------------

    def distinct(self, l, r):
        """半开区间 [l, r) 内不同值的个数：逐项收进集合再数大小。"""
        self._check(l, r)
        seen = set()
        for i in range(l, r):
            seen.add(self._data[i])
        return len(seen)

    def _counts(self, l, r):
        """把区间内每个值的出现次数逐项数出来，返回计数字典。"""
        counts = {}
        for i in range(l, r):
            v = self._data[i]
            counts[v] = counts.get(v, 0) + 1
        return counts

    def mode_count(self, l, r):
        """半开区间 [l, r) 内出现次数最多的值的出现次数。"""
        self._check(l, r)
        counts = self._counts(l, r)
        best = 0
        for c in counts.values():
            if c > best:
                best = c
        return best

    def sum_of_squares(self, l, r):
        """半开区间 [l, r) 内各值出现次数的平方和。"""
        self._check(l, r)
        counts = self._counts(l, r)
        total = 0
        for c in counts.values():
            total += c * c
        return total

    def brute_cost(self, l, r):
        """按朴素口径估一个查询要逐项扫过多少元素，用来对比指针移动量。"""
        self._check(l, r)
        return r - l
