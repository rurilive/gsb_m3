"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。默认样本永久保留；配置
window_seconds 后只统计滑动窗口内的样本。
"""

import threading
import time
from collections import deque


class Histogram:
    """直方图：observe 记样本，percentiles 取分位。

    window_seconds=None 时保留全部样本；配置后只统计最近
    window_seconds 秒内的样本，过期样本被惰性清理。
    clock 可注入（默认 time.monotonic），便于测试。
    """

    def __init__(self, window_seconds=None, clock=None):
        self._lock = threading.Lock()
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._values = []
        self._samples = deque()

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数。"""
        with self._lock:
            if self._window is None:
                self._values.append(value)
                return 0
            now = self._clock()
            self._samples.append((now, value))
            return self._evict_locked(now)

    def count(self):
        """当前（窗口内）样本总数。"""
        with self._lock:
            if self._window is None:
                return len(self._values)
            self._evict_locked(self._clock())
            return len(self._samples)

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。无样本抛 ValueError。"""
        with self._lock:
            if self._window is None:
                values = self._values
            else:
                self._evict_locked(self._clock())
                values = [v for _, v in self._samples]
            if not values:
                raise ValueError("no samples")
            data = sorted(values)
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """显式清理过期样本，返回清理数。无窗口时恒为 0。"""
        with self._lock:
            if self._window is None:
                return 0
            return self._evict_locked(self._clock())

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内分桶计数。

        返回 len(bucket_edges)+1 个计数；桶左闭右开，
        值等于边界归右桶。边界非严格递增抛 ValueError。
        """
        edges = list(bucket_edges)
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise ValueError("bucket_edges must be strictly increasing")
        with self._lock:
            if self._window is None:
                values = self._values
            else:
                self._evict_locked(self._clock())
                values = [v for _, v in self._samples]
            buckets = [0] * (len(edges) + 1)
            for v in values:
                buckets[_bucket_index(edges, v)] += 1
        return buckets

    def _evict_locked(self, now):
        """清掉 now - ts > window 的样本，返回清理数。调用方须持锁。"""
        evicted = 0
        samples = self._samples
        while samples and now - samples[0][0] > self._window:
            samples.popleft()
            evicted += 1
        return evicted


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight


def _bucket_index(edges, value):
    """左闭右开分桶：返回 value 落入的桶号（0..len(edges)）。"""
    lo, hi = 0, len(edges)
    while lo < hi:
        mid = (lo + hi) // 2
        if value < edges[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo
