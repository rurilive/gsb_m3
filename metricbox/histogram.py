"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。默认样本永久保留；配置
window_seconds 后只统计滑动窗口内的样本。
"""

import bisect
import threading
import time
from collections import deque


class Histogram:
    """直方图：observe 记样本，percentiles 取分位。

    window_seconds=None（默认）时样本永久保留；配置后
    count/percentiles/snapshot 只统计窗口内样本，窗口判定
    为 now - ts <= window_seconds（恰满窗口算窗口内）。
    clock 可注入，默认 time.monotonic。
    """

    def __init__(self, window_seconds=None, clock=None):
        self._lock = threading.Lock()
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._values = [] if window_seconds is None else deque()

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数。"""
        with self._lock:
            if self._window is None:
                self._values.append(value)
                return 0
            now = self._clock()
            self._values.append((now, value))
            return self._expire_locked(now)

    def count(self):
        """窗口内样本总数（无窗口时为全部样本）。"""
        with self._lock:
            return len(self._in_window_locked())

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。无样本抛 ValueError。"""
        with self._lock:
            values = self._in_window_locked()
            if not values:
                raise ValueError("no samples")
            data = sorted(values)
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """显式物理清理窗口外样本，返回清理数。无窗口时恒为 0。"""
        with self._lock:
            if self._window is None:
                return 0
            return self._expire_locked(self._clock())

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内分桶计数。

        返回 len(edges) + 1 个计数，值等于边界归右桶。
        边界非严格递增抛 ValueError。
        """
        edges = list(bucket_edges)
        if any(edges[i] >= edges[i + 1] for i in range(len(edges) - 1)):
            raise ValueError("bucket_edges must be strictly increasing")
        with self._lock:
            values = self._in_window_locked()
        buckets = [0] * (len(edges) + 1)
        for v in values:
            buckets[bisect.bisect_right(edges, v)] += 1
        return buckets

    def _expire_locked(self, now):
        """物理清理窗口外样本（队首最老），返回清理数。"""
        evicted = 0
        while self._values and now - self._values[0][0] > self._window:
            self._values.popleft()
            evicted += 1
        return evicted

    def _in_window_locked(self):
        """窗口内样本值：逻辑过滤，不做物理清理。"""
        if self._window is None:
            return list(self._values)
        now = self._clock()
        return [v for ts, v in self._values if now - ts <= self._window]


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
