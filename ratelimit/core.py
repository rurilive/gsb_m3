"""朴素固定窗限流器（改造前基线）。

当前能力：按固定时间窗口统计每个维度的请求量，每来一次请求就把它的
时间戳追加进该维度的列表，判定时线性扫描整张列表、数出落在当前窗口内
的个数再决定是否放行。结果正确，但对内的每一个时间戳都要重新看一遍，
底账越积越长，判定代价随历史记录线性增长。

本模块不含滑动窗口队列，也不含令牌桶，纯标准库，无外部依赖。
"""

DEFAULT_LABEL = "default"


class RateLimitError(Exception):
    """本模块参数与状态错误的基类。"""


class TimestampLimiter:
    """按固定时间窗口做准入判定的朴素限流器。

    每个维度维护一份按到达顺序追加的时间戳列表。allow 判定时先把当前
    时刻推进到本次请求时刻（时钟只增不减，回拨会被夹住），再把本次时间
    戳追加进列表，然后线性扫描整张列表数出落在窗口内的时间戳个数，个数
    不超过额度就放行，否则拒绝。为了后续能从上到下逐笔重新推演，每一笔
    判定都完整记录判定的时刻、落在窗口内的个数与是否放行。
    """

    def __init__(self, window, limit):
        if window <= 0:
            raise RateLimitError("window must be positive")
        if limit < 1:
            raise RateLimitError("limit must be at least 1")
        self._window = window
        self._limit = limit
        self._now = 0
        # 维度 -> 已放行的 (时间戳, 成本) 列表，按到达顺序追加
        self._entries = {}
        # 维度 -> 每一笔判定的记录列表
        self._history = {}

    @property
    def window(self):
        """窗口长度（时间单位）。"""
        return self._window

    @property
    def limit(self):
        """窗口内允许放行的额度。"""
        return self._limit

    @property
    def now(self):
        """内部单调时钟的当前值，初始为 0。"""
        return self._now

    def allow(self, now, cost=1, label=DEFAULT_LABEL):
        """在时刻 now 记一笔成本为 cost 的请求，返回这次是否放行。

        时钟只增不减：传入的 now 小于当前时钟时，当前时钟不动。
        窗口口径是左闭右开：时间戳 t 落在窗口内当且仅当
        now 减去 window 严格小于 t 且 t 小于等于 now。
        成本口径：窗口内已放行请求的成本之和与本笔成本相加不超过额度才
        放行，否则拒绝。只有放行的请求才进入底账，被拒的请求不占额度。
        拒绝时仍然记录下这次判定，便于重放。
        """
        if cost < 1:
            raise RateLimitError("cost must be at least 1")
        if now > self._now:
            self._now = now
        return self._judge(label, self._now, cost)

    def observed(self, at, label=DEFAULT_LABEL):
        """只看时刻 at 的窗口内计数，不改状态、不记判定。

        时钟以内部当前值为准，传入更大的 at 只用于这笔只读观测，
        不会推进内部时钟。
        """
        if at > self._now:
            self._now = at
        return self._observed_count(label, self._now)

    def total_rejected(self, label=DEFAULT_LABEL):
        """该维度累计被拒绝的笔数，按笔数计不按成本计。"""
        return sum(1 for rec in self._history.get(label, ()) if not rec[3])

    def history(self, label=DEFAULT_LABEL):
        """该维度全部判定的记录，按发生顺序排列。

        每条记录是四元素元组，依次为判定时刻、本笔成本、窗口内已放行成本
        之和、是否放行。返回一份新列表，改动它不影响内部状态。
        """
        return list(self._history.get(label, ()))

    def labels(self):
        """出现过的维度，按字符串升序排列的列表。"""
        return sorted(set(self._entries) | set(self._history))

    def _observed_count(self, label, at):
        """线性扫描该维度已放行的全部时间戳，数出落在窗口内的笔数。"""
        low = at - self._window
        n = 0
        for t, _cost in self._entries.get(label, ()):
            if low < t <= at:
                n += 1
        return n

    def _judge(self, label, at, cost):
        """判定一笔请求：线性扫描整表累加窗口内成本，返回是否放行。

        窗口内已放行请求的成本之和与本笔成本相加不超过额度才放行；放行的
        请求连同成本追加进底账，被拒的请求不留痕在底账里。无论放行与否都
        记一条判定，便于从上到下逐笔重放。
        """
        low = at - self._window
        used = 0
        for t, c in self._entries.get(label, ()):
            if low < t <= at:
                used += c
        ok = used + cost <= self._limit
        self._history.setdefault(label, []).append((at, cost, used, ok))
        if ok:
            self._entries.setdefault(label, []).append((at, cost))
        return ok


def naive_scan(stamps, window, at):
    """朴素口径的独立实现：线性扫描一批时间戳，返回落在窗口内的个数。

    时间戳 t 落在窗口内当且仅当 at 减去 window 严格小于 t 且
    t 小于等于 at。本函数不依赖任何对象状态，可用来与限流器逐项核对。
    """
    low = at - window
    n = 0
    for t in stamps:
        if low < t <= at:
            n += 1
    return n
