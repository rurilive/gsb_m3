"""朴素流式统计实现 NaiveStats。

改造前的基线：内部就是一个 float 列表，任何一次查询都把整段数据
重新排序再按位置取值，简单、直观，但数据一多就慢。

纯标准库，无外部依赖。
"""


class StatError(Exception):
    """统计库的参数错误基类。"""


class NaiveStats:
    """朴素流式统计：把推入的值存进列表，查询时就地重排。

    空数据查询的约定：mean、median、min、max 在没有任何数据时都返回 None。
    """

    def __init__(self):
        self._values = []

    def push(self, x):
        """追加一个数值。非数值（含布尔）抛出 StatError。"""
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise StatError("push 只接受数值")
        self._values.append(float(x))

    def count(self):
        """已推入的数值个数。"""
        return len(self._values)

    def mean(self):
        """算术平均；空数据返回 None。"""
        if not self._values:
            return None
        return sum(self._values) / len(self._values)

    def median(self):
        """中位数；空数据返回 None。

        每次调用都先把整段排序，再按位置取值：奇数个取正中间那个，
        偶数个取中间两个的算术平均。
        """
        if not self._values:
            return None
        ordered = sorted(self._values)
        n = len(ordered)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def min(self):
        """最小值；空数据返回 None。排序后取端。"""
        if not self._values:
            return None
        return sorted(self._values)[0]

    def max(self):
        """最大值；空数据返回 None。排序后取端。"""
        if not self._values:
            return None
        return sorted(self._values)[-1]

    def sorted_values(self):
        """返回排序后的副本，改动副本不影响内部数据。"""
        return sorted(self._values)
