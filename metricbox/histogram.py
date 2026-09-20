"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。

默认样本永久保留；构造时传入 ``window_seconds`` 后切换为滑动窗口：
``count``/``percentiles``/``snapshot`` 只统计窗口内样本。窗口判定使用
可注入时钟（默认 ``time.monotonic``），恰满 ``window_seconds`` 的样本
仍算窗口内。过期样本惰性清理，也可显式调用 ``compact``。
"""

import bisect
import threading
import time


class Histogram:
    """全量样本或滑动窗口直方图：observe 记样本，percentiles 取分位。"""

    def __init__(self, window_seconds=None, clock=None):
        if window_seconds is not None:
            if isinstance(window_seconds, bool) or not isinstance(
                window_seconds, (int, float)
            ):
                raise TypeError("window_seconds must be a number")
            if window_seconds <= 0:
                raise ValueError("window_seconds must be positive")
        if window_seconds is not None and clock is None:
            clock = time.monotonic
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._values = []
        self._timestamps = []

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数（非窗口模式恒为 0）。"""
        with self._lock:
            if self._window is None:
                self._values.append(value)
                return 0
            now = self._clock()
            cutoff = now - self._window
            stale = bisect.bisect_left(self._timestamps, cutoff)
            if stale:
                del self._timestamps[:stale]
                del self._values[:stale]
            self._timestamps.append(now)
            self._values.append(value)
            return stale

    def count(self):
        """当前窗口内样本总数（非窗口模式为全部样本数）。"""
        with self._lock:
            return len(self._live_values())

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。窗口内无样本抛 ValueError。"""
        with self._lock:
            data = sorted(self._live_values())
            if not data:
                raise ValueError("no samples")
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """物理清理已滑出窗口的样本，返回被清理的样本数（非窗口模式恒为 0）。"""
        with self._lock:
            if self._window is None:
                return 0
            cutoff = self._clock() - self._window
            stale = bisect.bisect_left(self._timestamps, cutoff)
            if stale:
                del self._timestamps[:stale]
                del self._values[:stale]
            return stale

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内样本的分桶计数。

        返回长度为 ``len(bucket_edges) + 1`` 的 list，下标 i 的桶为
        ``(edges[i-1], edges[i]]``（首桶无上界、尾桶无下界），值恰好
        等于边界时归入右侧桶，即 ``bisect_right`` 规则。
        """
        edges = list(bucket_edges)
        if any(edges[i] >= edges[i + 1] for i in range(len(edges) - 1)):
            raise ValueError("bucket_edges must be strictly increasing")
        counts = [0] * (len(edges) + 1)
        with self._lock:
            for value in self._live_values():
                counts[bisect.bisect_right(edges, value)] += 1
        return counts

    def _live_values(self):
        """调用方须持锁；返回窗口内样本（不做任何清理）。"""
        if self._window is None:
            return self._values
        cutoff = self._clock() - self._window
        start = bisect.bisect_left(self._timestamps, cutoff)
        return self._values[start:]


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
