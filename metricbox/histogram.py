"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。

默认样本永久保留；传入 window_seconds 后样本带时间戳，
count/percentiles/snapshot 只统计窗口内样本。清理是惰性的：
每次读写顺带丢弃过期样本，observe 返回本次挤出的样本数；
也可以调用 compact() 显式清理。时钟可注入，默认 monotonic。
"""

import bisect
import threading
import time


class Histogram:
    """线程安全直方图：observe 记样本，percentiles 取分位。

    window_seconds=None（默认）时样本永久保留，行为与全量模式一致；
    配置窗口后只统计最近 window_seconds 秒内的样本，恰满
    window_seconds 的样本仍算窗口内。clock 可注入，返回单调递增
    的时间（秒），默认 time.monotonic。
    """

    def __init__(self, window_seconds=None, clock=None):
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive or None")
        self._window = window_seconds
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._values = []
        self._timestamps = [] if window_seconds is not None else None

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数。

        未配置窗口时始终返回 0。
        """
        with self._lock:
            if self._window is None:
                self._values.append(value)
                return 0
            now = self._clock()
            evicted = self._evict_locked(now)
            self._timestamps.append(now)
            self._values.append(value)
            return evicted

    def count(self):
        """当前（窗口内）样本总数。"""
        with self._lock:
            if self._window is None:
                return len(self._values)
            self._evict_locked(self._clock())
            return len(self._values)

    def compact(self):
        """显式丢弃过期样本，返回被清理的样本数。

        未配置窗口、或无样本过期时返回 0。
        """
        with self._lock:
            if self._window is None:
                return 0
            return self._evict_locked(self._clock())

    def snapshot(self, bucket_edges):
        """按严格递增边界导出（窗口内）样本的分桶计数。

        n 个边界分出 n+1 个桶：(-inf, edges[0])、[edges[0], edges[1])、
        ...、[edges[-1], +inf)，即值等于边界归入右侧桶。返回各桶
        样本数组成的 list，长度为 len(bucket_edges) + 1。
        """
        edges = list(bucket_edges)
        if any(edges[i] >= edges[i + 1] for i in range(len(edges) - 1)):
            raise ValueError("bucket_edges must be strictly increasing")
        with self._lock:
            if self._window is not None:
                self._evict_locked(self._clock())
            counts = [0] * (len(edges) + 1)
            for value in self._values:
                counts[bisect.bisect_right(edges, value)] += 1
        return counts

    def _evict_locked(self, now):
        """丢弃早于窗口下界的样本，返回挤出数量。调用方持锁。"""
        if self._window is None:
            return 0
        cutoff = now - self._window
        expired = bisect.bisect_left(self._timestamps, cutoff)
        if expired:
            del self._timestamps[:expired]
            del self._values[:expired]
        return expired

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。无样本抛 ValueError。"""
        with self._lock:
            if self._window is not None:
                self._evict_locked(self._clock())
            if not self._values:
                raise ValueError("no samples")
            data = sorted(self._values)
        return {p: _interpolate(data, p) for p in fractions}


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
