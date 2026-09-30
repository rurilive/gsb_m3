"""cdqx.core：三维偏序计数的朴素实现（改造前基线）。

给定若干带三个属性的点，眼下一律用最直白的两两比较把答案算出来：

  - counts_weak    每个点被多少个点在各维都不超过它支配：对每个点扫全部点；
  - counts_strict  每个点被多少个点在各维都严格小于它支配：同样逐个比对；
  - pairs_weak     全部三维偏序对个数（不超过口径）：把每点的计数加起来；
  - pairs_strict   全部三维偏序对个数（严格小于口径）：把每点的计数加起来；
  - order_by_axis  按某一维排序后的点下标次序：反复扫描取最小值，两两枚举；
  - weighted_counts_weak    按点权加权的偏序计数（不超过口径）：逐对累加权值；
  - weighted_counts_strict  按点权加权的偏序计数（严格小于口径）：逐对累加权值。

这些做法直观可靠，结果一眼能看穿，可点数一多就是平方量级，规模一大就跑
不完。本文件是改造前的基线，朴素路径在改造之后不得删除，新的分治路径必须
与它对同一批输入给出的结果逐项对齐。

计数：last_naive_comparisons 记录最近一次调用里两两比较的点对次数；
last_bit_probe_count 预留给改造后的分治路径统计树状数组访问次数。

异常统一继承 CdqxErro 基类：InputErro。
"""


class CdqxErro(Exception):
    """三维偏序库所有异常的基类，非法输入与非法操作一律快速失败。"""


class InputErro(CdqxErro):
    """输入非法：点不是三元组、属性不是整数、维度下标越界、权值不是整数。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 InputErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _as_point(item, where):
    """把入参规整成三元组，逐维取整。非三项序列即抛 InputErro。"""
    if item is None:
        raise InputErro("%s：点必须显式给出，不能为 None" % where)
    try:
        parts = list(item)
    except TypeError:
        raise InputErro("%s：点必须是可迭代的三元组，收到 %r" % (where, item))
    if len(parts) != 3:
        raise InputErro("%s：点必须恰有三个属性维度，收到 %d 维" % (where, len(parts)))
    return tuple(_as_int(parts[k], "%s第%d维" % (where, k + 1)) for k in range(3))


def _norm_points(points):
    """点集规整成三元组的元组，逐点逐维校验为整数。"""
    if points is None:
        raise InputErro("点集：必须显式给出，不能为 None")
    try:
        items = list(points)
    except TypeError:
        raise InputErro("点集：必须是可迭代对象，收到 %r" % (points,))
    return tuple(_as_point(item, "点集第%d个点" % (i + 1)) for i, item in enumerate(items))


def _norm_weights(weights, size):
    """权值序列规整成整数元组，长度必须与点数一致。"""
    if weights is None:
        raise InputErro("权值序列：必须显式给出，不能为 None")
    try:
        items = list(weights)
    except TypeError:
        raise InputErro("权值序列：必须是可迭代对象，收到 %r" % (weights,))
    if len(items) != size:
        raise InputErro("权值序列：长度必须与点数一致，收到 %d 对 %d" % (len(items), size))
    return tuple(_as_int(item, "权值第%d项" % (i + 1)) for i, item in enumerate(items))


class DominanceCounter:
    """一组带三个属性的点，用朴素两两比较回答三维偏序计数。"""

    def __init__(self, points, weights=None):
        self._points = _norm_points(points)
        if weights is None:
            self._weights = tuple(1 for _ in self._points)
        else:
            self._weights = _norm_weights(weights, len(self._points))
        self._last_naive = 0
        self._last_bit_probe = 0

    @property
    def points(self):
        return self._points

    @property
    def weights(self):
        return self._weights

    @property
    def size(self):
        return len(self._points)

    @property
    def last_naive_comparisons(self):
        """最近一次调用里两两比较的点对次数。"""
        return self._last_naive

    @property
    def last_bit_probe_count(self):
        """最近一次调用里树状数组访问次数，基线路径恒为零。"""
        return self._last_bit_probe

    def _reset_counters(self):
        self._last_naive = 0
        self._last_bit_probe = 0

    def _count(self, strict):
        """逐点扫全部点，按口径累加被支配的个数。"""
        self._reset_counters()
        n = len(self._points)
        out = []
        for i in range(n):
            pi = self._points[i]
            hit = 0
            for j in range(n):
                self._last_naive += 1
                if j == i:
                    continue
                pj = self._points[j]
                if strict:
                    ok = pj[0] < pi[0] and pj[1] < pi[1] and pj[2] < pi[2]
                else:
                    ok = pj[0] <= pi[0] and pj[1] <= pi[1] and pj[2] <= pi[2]
                if ok:
                    hit += 1
            out.append(hit)
        return tuple(out)

    def counts_weak(self):
        """每点被多少个点在各维都不超过它支配。"""
        return self._count(False)

    def counts_strict(self):
        """每点被多少个点在各维都严格小于它支配。"""
        return self._count(True)

    def pairs_weak(self):
        """全部三维偏序对个数（不超过口径）。"""
        return sum(self.counts_weak())

    def pairs_strict(self):
        """全部三维偏序对个数（严格小于口径）。"""
        return sum(self.counts_strict())

    def order_by_axis(self, axis):
        """按第 axis 维（从零起）升序给出点下标的次序，同值按原点序稳定排列。

        朴素做法：反复扫描剩余下标取当前最小者，全程两两枚举，平方量级。
        """
        axis = _as_int(axis, "维度下标")
        if axis < 0 or axis > 2:
            raise InputErro("维度下标：必须在零到二之间，收到 %r" % (axis,))
        self._reset_counters()
        n = len(self._points)
        remaining = list(range(n))
        out = []
        while remaining:
            best = 0
            for k in range(1, len(remaining)):
                self._last_naive += 1
                cand = remaining[k]
                cur = remaining[best]
                if (self._points[cand][axis], cand) < (self._points[cur][axis], cur):
                    best = k
            out.append(remaining.pop(best))
        return tuple(out)

    def _weighted(self, strict):
        """逐点扫全部点，按口径累加被支配点的权值。"""
        self._reset_counters()
        n = len(self._points)
        out = []
        for i in range(n):
            pi = self._points[i]
            total = 0
            for j in range(n):
                self._last_naive += 1
                if j == i:
                    continue
                pj = self._points[j]
                if strict:
                    ok = pj[0] < pi[0] and pj[1] < pi[1] and pj[2] < pi[2]
                else:
                    ok = pj[0] <= pi[0] and pj[1] <= pi[1] and pj[2] <= pi[2]
                if ok:
                    total += self._weights[j]
            out.append(total)
        return tuple(out)

    def weighted_counts_weak(self):
        """按点权加权的偏序计数，口径为各维都不超过。"""
        return self._weighted(False)

    def weighted_counts_strict(self):
        """按点权加权的偏序计数，口径为各维都严格小于。"""
        return self._weighted(True)
