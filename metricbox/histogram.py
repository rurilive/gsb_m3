"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。默认样本永久保留；配置
window_seconds 后只统计滑动窗口内的样本。
"""

import bisect
import threading
import time


class Histogram:
    """直方图：observe 记样本，percentiles 取分位。

    window_seconds 为 None 时保留全部样本；否则只统计最近
    window_seconds 秒内的样本（恰满窗口算窗口内）。
    clock 可注入，默认 time.monotonic。
    """

    def __init__(self, window_seconds=None, clock=None):
        self._lock = threading.Lock()
        self._samples = []
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数。"""
        with self._lock:
            now = self._clock()
            evicted = self._purge_locked(now)
            self._samples.append((now, value))
            return evicted

    def count(self):
        """窗口内样本总数（不配置窗口时为全部样本）。"""
        with self._lock:
            return len(self._in_window_locked(self._clock()))

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。窗口内无样本抛 ValueError。"""
        with self._lock:
            data = sorted(v for _, v in self._in_window_locked(self._clock()))
            if not data:
                raise ValueError("no samples")
        return {p: _interpolate(data, p) for p in fractions}

    def snapshot(self, bucket_edges):
        """按严格递增边界对窗口内样本分桶，返回 len(edges)+1 个计数。

        值等于边界归右桶；边界非严格递增抛 ValueError。
        """
        edges = list(bucket_edges)
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise ValueError("bucket_edges 必须严格递增")
        with self._lock:
            values = [v for _, v in self._in_window_locked(self._clock())]
        buckets = [0] * (len(edges) + 1)
        for v in values:
            buckets[bisect.bisect_right(edges, v)] += 1
        return buckets

    def compact(self):
        """显式清理窗口外样本，返回清理数。"""
        with self._lock:
            return self._purge_locked(self._clock())

    def _in_window_locked(self, now):
        if self._window is None:
            return list(self._samples)
        return [s for s in self._samples if now - s[0] <= self._window]

    def _purge_locked(self, now):
        if self._window is None:
            return 0
        kept = [s for s in self._samples if now - s[0] <= self._window]
        evicted = len(self._samples) - len(kept)
        self._samples[:] = kept
        return evicted


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
