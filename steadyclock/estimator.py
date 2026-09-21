"""偏移估计：看对端墙上钟比本机快多少。

OffsetProbe 是保留的单发口径：跑一次往返，拿对端收到请求那一下的读数
减去本地发出那一下的读数，不滤波，也不给质量信息。

OffsetEstimator 是多次测量的口径：每趟往返算出 NTP 式偏移与往返时延，
喂给 filter.py 的 OffsetFilter 做离群剔除与平滑，sample() 交出一个
Estimate，带 offset、error_bound、confidence 三个数。
"""

from typing import NamedTuple

from steadyclock.filter import OffsetFilter


class Estimate(NamedTuple):
    """一次估计的结果：偏移、兜得住真值的误差界、置信度。"""

    offset: float
    error_bound: float
    confidence: float


class OffsetProbe:
    """单次偏移探针。"""

    def __init__(self, loopback):
        self._loopback = loopback

    def probe(self):
        """跑一次往返，返回一个偏移估计，单位秒。"""
        t0, t1, _t2, _t3 = self._loopback.exchange()
        return t1 - t0


class OffsetEstimator:
    """多次测量的偏移估计器。

    每趟往返拿到四个时间戳：t0 本地发出、t1 对端收到、t2 对端发出、
    t3 本地收到。偏移取 ((t1 - t0) + (t2 - t3)) / 2，往返时延取
    (t3 - t0) - (t2 - t1)，两个本地戳都打在单调钟上，校时拨不动。
    """

    def __init__(self, loopback, window=64):
        self._loopback = loopback
        self._filter = OffsetFilter(window=window)

    def sample(self):
        """跑一趟往返，喂进滤波器，交出当前的 Estimate。"""
        t0, t1, t2, t3 = self._loopback.exchange()
        offset = ((t1 - t0) + (t2 - t3)) / 2.0
        rtt = (t3 - t0) - (t2 - t1)
        self._filter.add(offset, rtt)
        offset, error_bound, confidence = self._filter.estimate()
        return Estimate(offset=offset, error_bound=error_bound,
                        confidence=confidence)
