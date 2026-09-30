"""朴素流式分位数实现 NaivePercentileStream。

改造前的基线：内部就是一个 float 列表，每来一次查询就把整段数据
复制一份排序再按位置取值，结果对，但接收越多查询越慢。

纯标准库，无外部依赖。
"""


class StreamError(Exception):
    """流式统计库的参数错误基类。"""


class NaivePercentileStream:
    """朴素流式分位数：把推入的值存进列表，查询时全量排序取值。

    空数据查询的约定：median、quantile、min、max 在没有任何数据时返回 None。
    偶数个取中位数时，取中间两个的算术平均，写死不改。
    分位取值口径：把数据升序排列成长度 n 的序列，位置下标等于 q 乘以 n 减一
    再除以一百后向下取整，两端分别落在最小与最大上，中间不做插值。
    """

    def __init__(self):
        self._values = []

    def push(self, x):
        """追加一个数值。非数值（含布尔）抛出 StreamError。"""
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise StreamError("push 只接受数值")
        self._values.append(float(x))

    def count(self):
        """已推入的数值个数。"""
        return len(self._values)

    def _ordered(self):
        """把当前全部数据复制一份并升序排列。"""
        return sorted(self._values)

    def median(self):
        """中位数；空数据返回 None。

        奇数个取正中间那个；偶数个取中间两个的算术平均。
        """
        if not self._values:
            return None
        ordered = self._ordered()
        n = len(ordered)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def quantile(self, q):
        """按位置取分位数；空数据返回 None。

        q 是 0 到 100 的整数（不含布尔），越界或非整数抛出 StreamError。
        位置下标为 q 乘以 n 减一再除以一百后向下取整，落在 0 与 n 减 1 之间。
        """
        if isinstance(q, bool) or not isinstance(q, int):
            raise StreamError("分位必须是整数")
        if q < 0 or q > 100:
            raise StreamError("分位必须在 0 到 100 之间")
        if not self._values:
            return None
        ordered = self._ordered()
        n = len(ordered)
        idx = (q * (n - 1)) // 100
        return ordered[idx]

    def min(self):
        """最小值；空数据返回 None。排序后取端。"""
        if not self._values:
            return None
        return self._ordered()[0]

    def max(self):
        """最大值；空数据返回 None。排序后取端。"""
        if not self._values:
            return None
        return self._ordered()[-1]

    def sorted_values(self):
        """返回排序后的副本，改动副本不影响内部数据。"""
        return sorted(self._values)
