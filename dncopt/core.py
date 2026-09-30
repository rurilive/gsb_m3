"""dncopt.core：分段最优划分的朴素实现（改造前基线）。

给定一条非负整数代价序列，把它按原顺序划分成指定组数，每组是一段连续
元素，一段的总代价记为该段元素之和的平方，一次划分的总代价是各组代价
之和，目标是求总代价最小的划分。组内元素次序不变，每组至少一个元素。

眼下只有最朴素的一条路子：

  - seg_sum(i, j)      直接累加第 i 到第 j 个元素的代价，逐项相加；
  - seg_cost(i, j)     在该段之和的基础上取平方，得到这一段的总代价；
  - segmented_dp(g)    对每一组、每个前缀，枚举全部可能的上一刀位置 j，
                       把前 j 个元素分成 g 减一 组的最小代价，加上第 j 加一
                       到第 i 个元素这一段的代价，取最小；
  - decision_points(g) 与 segmented_dp 同一套枚举，同时记下每个状态取到最小
                       总代价的那个切割点 j，并列时取下标最小者；
  - min_cost(g)        取整条序列分成 g 组的最小总代价。

这些做法直白、结果对，但对每一组、每个前缀都要枚举全部切割点，组数与
长度一大就是平方乃至更高量级，规模一长就跑不完。本文件是改造前的基线，
朴素路径在改造之后不得删除，新的分治路径必须与它对同一批输入逐项对齐。

计数：naive_op_visits 记录最近一次调用里枚举切割点的次数。

异常统一继承 DncoptErro 基类：InputErro。
"""


class DncoptErro(Exception):
    """分段最优划分库所有异常的基类，非法输入与非法操作一律快速失败。"""


class InputErro(DncoptErro):
    """输入非法：代价不是整数、代价为负、组数不是整数或超出可行范围。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 InputErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _norm_costs(costs):
    """代价序列规整成非负整数的元组。None、非可迭代、负值一律抛 InputErro。"""
    if costs is None:
        raise InputErro("代价序列：必须显式给出，不能为 None")
    try:
        items = list(costs)
    except TypeError:
        raise InputErro("代价序列：必须是可迭代对象，收到 %r" % (costs,))
    out = []
    for i, item in enumerate(items):
        v = _as_int(item, "代价第%d项" % (i + 1))
        if v < 0:
            raise InputErro("代价第%d项：必须是非负整数，收到 %r" % (i + 1, v))
        out.append(v)
    return tuple(out)


class Optimizer:
    """一条代价序列，用朴素枚举回答分组最小代价与最优切割点。"""

    def __init__(self, costs):
        self._costs = _norm_costs(costs)
        pref = [0]
        acc = 0
        for c in self._costs:
            acc += c
            pref.append(acc)
        self._prefix = tuple(pref)
        self._naive_visits = 0

    @property
    def costs(self):
        return self._costs

    @property
    def size(self):
        """元素的个数。"""
        return len(self._costs)

    @property
    def naive_op_visits(self):
        """最近一次调用里枚举切割点的次数。"""
        return self._naive_visits

    def seg_sum(self, i, j):
        """第 i 到第 j 个元素这一段的和，下标从一起算，两端都取到。

        朴素做法：直接对该段逐项累加，段一长就是线性量级。
        """
        i = _as_int(i, "左端下标")
        j = _as_int(j, "右端下标")
        n = len(self._costs)
        if i < 1 or j > n or i > j:
            raise InputErro(
                "区间：必须满足 一 小于等于 左端 小于等于 右端 小于等于 %d，收到 %r 到 %r"
                % (n, i, j))
        total = 0
        for k in range(i - 1, j):
            total += self._costs[k]
        return total

    def seg_cost(self, i, j):
        """第 i 到第 j 个元素这一段的总代价，记为该段和的平方。"""
        s = self.seg_sum(i, j)
        return s * s

    def _segment_cost(self, i, j):
        """前缀和口径的第 i 到第 j 段代价，供内部枚举复用，不做下标校验。"""
        s = self._prefix[j] - self._prefix[i - 1]
        return s * s

    def _dp(self, groups, want_decisions):
        """朴素自底向上：逐组逐前缀枚举全部上一刀位置取最小。

        dp[g][i] 表示把前 i 个元素分成 g 组的最小总代价，无法划分时为 None。
        dec[g][i] 是对应的切割点 j（前 j 个元素归前 g 减一 组），并列取最小。
        """
        groups = _as_int(groups, "组数")
        n = len(self._costs)
        if groups < 0:
            raise InputErro("组数：必须是非负整数，收到 %r" % (groups,))
        if groups > n:
            raise InputErro("组数：不能超过元素个数 %d，收到 %r" % (n, groups))
        self._naive_visits = 0
        dp = [[None] * (n + 1) for _ in range(groups + 1)]
        dec = [[None] * (n + 1) for _ in range(groups + 1)] if want_decisions else None
        dp[0][0] = 0
        for g in range(1, groups + 1):
            row = dp[g]
            prev = dp[g - 1]
            drow = dec[g] if want_decisions else None
            for i in range(g, n + 1):
                best = None
                best_j = None
                for j in range(g - 1, i):
                    self._naive_visits += 1
                    base = prev[j]
                    if base is None:
                        continue
                    val = base + self._segment_cost(j + 1, i)
                    if best is None or val < best:
                        best = val
                        best_j = j
                row[i] = best
                if want_decisions:
                    drow[i] = best_j
        return dp, dec

    def segmented_dp(self, groups):
        """把整条序列分成 groups 组的最小代价表，按组逐层给出。

        返回长度为 groups 加一 的元组，第 g 项是长度 size 加一 的元组，
        下标 i 处为前 i 个元素分成 g 组的最小总代价，无法划分处为 None。
        """
        dp, _ = self._dp(groups, False)
        return tuple(tuple(row) for row in dp)

    def decision_points(self, groups):
        """与 segmented_dp 并行的最优切割点表，并列时取下标最小者。

        返回长度为 groups 加一 的元组，第 g 项下标 i 处为前 i 个元素分成 g 组
        取到最小总代价的切割点 j，无法划分或不可达处为 None。
        """
        _, dec = self._dp(groups, True)
        return tuple(tuple(row) for row in dec)

    def min_cost(self, groups):
        """把整条序列分成 groups 组的最小总代价，无法划分时返回 None。"""
        dp, _ = self._dp(groups, False)
        n = len(self._costs)
        return dp[groups][n]
