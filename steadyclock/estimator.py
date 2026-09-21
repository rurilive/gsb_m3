"""对端钟差估计：单发探针与多次测量的估计器。

OffsetProbe 是留着兼容的一锤子买卖：跑一次往返，拿对端收到请求那一下
的读数减去本地发出那一下的读数，不滤波，也不给任何质量信息。

OffsetEstimator 是升级口径：每趟往返用四个时间戳算一个钟差样本
（请求与响应两个方向的不对称互相抵消一半），交给 OffsetFilter 做
离群剔除与平滑；收敛之后锁定读数不再抖动，除非有证据表明对端真值
迁移（比如对端重新校时），才解锁重新收敛。每次 sample() 交出
Estimate：offset 是估计值，error_bound 兜得住真值，confidence
反映最近窗口里干净样本的占比。
"""

from collections import namedtuple

from steadyclock.filter import OffsetFilter

Estimate = namedtuple("Estimate", ("offset", "error_bound", "confidence"))


class OffsetProbe:
    """单次偏移探针。"""

    def __init__(self, loopback):
        self._loopback = loopback

    def probe(self):
        """跑一次往返，返回一个偏移估计，单位秒。"""
        t0, t1, _t2, _t3 = self._loopback.exchange()
        return t1 - t0


class OffsetEstimator:
    """多次测量的偏移估计器：每趟往返喂一个样本，收敛后锁定。

    tolerance 是收敛门槛：窗口喂满且幸存样本的离散度压进它，估计
    就锁定，之后 offset 与 error_bound 不再抖动；滤波值偏离锁定值
    超出两边误差界之和时，视为真值迁移，解锁重新收敛。
    """

    def __init__(self, loopback, window=32, select=8, tolerance=0.005):
        self._loopback = loopback
        self._filter = OffsetFilter(window=window, select=select)
        self._tolerance = float(tolerance)
        self._held = None
        self._converged = False

    @property
    def converged(self):
        """估计是否已锁定。"""
        return self._converged

    def sample(self):
        """跑一次往返，交出当前最佳估计 Estimate。"""
        t0, t1, t2, t3 = self._loopback.exchange()
        offset = ((t1 - t0) + (t2 - t3)) / 2.0
        delay = (t3 - t0) - (t2 - t1)
        self._filter.add(offset, delay)
        result = self._filter.evaluate()
        if not self._converged:
            if (
                len(self._filter) >= self._filter.window
                and result.spread <= self._tolerance
            ):
                self._converged = True
                self._held = (result.offset, result.error_bound)
            else:
                return Estimate(result.offset, result.error_bound, result.confidence)
        held_offset, held_bound = self._held
        if abs(result.offset - held_offset) > held_bound + result.error_bound:
            self._filter.reset()
            self._held = None
            self._converged = False
            return Estimate(result.offset, result.error_bound, result.confidence)
        return Estimate(held_offset, held_bound, result.confidence)
