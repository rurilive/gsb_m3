"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。默认样本永久保留；配置
window_seconds 后只统计滑动窗口内的样本，过期样本惰性清理。
"""

import bisect
import threading
import time
from collections import deque


class Histogram:
    """直方图：observe 记样本，percentiles 取分位。

    window_seconds=None 时保留全部样本；配置后只统计
    窗口内样本，时钟可通过 clock 注入（默认 time.monotonic）。
    """

    def __init__(self, window_seconds=None, clock=None):
        if window_seconds is not None and window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._lock = threading.Lock()
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._samples = deque()

    def observe(self, value):
        """记录一个样本。配置窗口时返回本次被挤出的样本数。"""
        with self._lock:
            now = self._clock()
            self._samples.append((now, value))
            if self._window is None:
                return None
            return self._evict(now)

    def count(self):
        """当前窗口内样本总数。"""
        with self._lock:
            self._evict(self._clock())
            return len(self._samples)

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。窗口内无样本抛 ValueError。"""
        with self._lock:
            self._evict(self._clock())
            if not self._samples:
                raise ValueError("no samples")
            data = sorted(v for _, v in self._samples)
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """显式清理过期样本，返回清理数。无窗口时恒为 0。"""
        with self._lock:
            return self._evict(self._clock())

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内分桶计数，值等于边界归右桶。

        返回 len(bucket_edges) + 1 个计数。
        """
        edges = list(bucket_edges)
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise ValueError("bucket_edges must be strictly increasing")
        with self._lock:
            self._evict(self._clock())
            buckets = [0] * (len(edges) + 1)
            for _, v in self._samples:
                buckets[bisect.bisect_right(edges, v)] += 1
            return buckets

    def _evict(self, now):
        """挤出窗口外样本（调用方须持锁），返回挤出数。"""
        if self._window is None:
            return 0
        evicted = 0
        while self._samples and now - self._samples[0][0] > self._window:
            self._samples.popleft()
            evicted += 1
        return evicted


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
