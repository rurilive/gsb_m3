"""全量样本集合。

样本一条不落地存在列表里，查询时才排序。样本量在内存装得下时
用它最省事，分位值就是精确值，还能给别的估算器当参考。
"""

import bisect
import math

from qsketch.errors import EmptySetError, SketchError


def to_sample(value):
    """把一条输入规整成样本。

    接受 int 和 float，转成 float 存。bool 虽然也是 int 的子类，
    但落到延迟统计里是误传，直接拒绝；字符串之类更不必说。
    nan 和 inf 也拒绝，排序和插值都靠不住。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SketchError("sample must be a real number, got %r" % (value,))
    sample = float(value)
    if not math.isfinite(sample):
        raise SketchError("sample must be finite, got %r" % (value,))
    return sample


def check_quantile(q):
    """校验分位参数，返回 float。"""
    if isinstance(q, bool) or not isinstance(q, (int, float)):
        raise SketchError("quantile must be a real number, got %r" % (q,))
    q = float(q)
    if not 0.0 <= q <= 1.0:
        raise SketchError("quantile out of range: %r" % (q,))
    return q


def quantile_of_sorted(ordered, q):
    """有序样本上的线性插值分位。

    位置 pos = q * (n - 1)，在 pos 两侧的样本之间线性插值；
    q=0 取最小，q=1 取最大。ordered 必须是排好序的非空列表。
    """
    q = check_quantile(q)
    n = len(ordered)
    if n == 0:
        raise EmptySetError("quantile of empty set")
    if n == 1:
        return float(ordered[0])
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


class SampleSet:
    """全量留存的分位统计，单线程使用。"""

    def __init__(self, values=None):
        self._values = []
        if values is not None:
            for value in values:
                self.add(value)

    # ---- 收样本 ----

    def add(self, value):
        """收一条样本，返回当前样本数。"""
        self._values.append(to_sample(value))
        return len(self._values)

    # ---- 读数 ----

    def count(self):
        return len(self._values)

    def values(self):
        """样本副本，顺序与加入时一致。"""
        return list(self._values)

    def mean(self):
        if not self._values:
            raise EmptySetError("mean of empty set")
        return sum(self._values) / len(self._values)

    def minimum(self):
        if not self._values:
            raise EmptySetError("minimum of empty set")
        return min(self._values)

    def maximum(self):
        if not self._values:
            raise EmptySetError("maximum of empty set")
        return max(self._values)

    def quantile(self, q):
        """q 分位，精确值：全量排序后线性插值。"""
        return quantile_of_sorted(sorted(self._values), q)

    def cdf(self, x):
        """样本里小于等于 x 的占比。"""
        x = to_sample(x)
        if not self._values:
            raise EmptySetError("cdf of empty set")
        ordered = sorted(self._values)
        return bisect.bisect_right(ordered, x) / len(ordered)

    def stats(self):
        """count / mean / min / max 的快照。"""
        if not self._values:
            raise EmptySetError("stats of empty set")
        ordered = sorted(self._values)
        return {
            "count": len(ordered),
            "mean": sum(ordered) / len(ordered),
            "min": ordered[0],
            "max": ordered[-1],
        }

    # ---- 合并 ----

    def merge(self, other):
        """并进另一个 SampleSet，返回新对象，两边都不动。"""
        if not isinstance(other, SampleSet):
            raise SketchError(
                "merge expects a SampleSet, got %s" % type(other).__name__)
        merged = SampleSet()
        merged._values = list(self._values) + list(other._values)
        return merged
