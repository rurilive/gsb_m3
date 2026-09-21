"""滑动窗口聚合。

窗口长度固定，区间取闭开 [start, end)，按事件时间（水位线）推进，
与到达时刻无关，重放同一事件流结果可复现。
窗口关闭时聚合结果记入产出缓冲，支持相邻已关闭窗口合并。
"""

import math
import threading
import time
from collections import deque, namedtuple

ClosedWindow = namedtuple("ClosedWindow", ["start", "end", "total"])
"""已关闭窗口的产出记录：区间 [start, end) 与窗口内计数和。"""


class WindowedCounter:
    """固定长度窗口计数器，窗口按事件时间推进。

    size: 窗口长度（秒）。
    clock: 注入时钟，只记到达时刻，不影响窗口推进。
    late_policy: 落在已关闭窗口（早于左边界）的迟到事件策略，
        "drop" 丢弃，"count" 计入 late_total；两种都记 late_count。
    keep_outputs: 产出缓冲保留的已关闭窗口条数，超出的最老一条过期。
    on_close: 可选回调，窗口关闭时以 ClosedWindow 调用。
    """

    def __init__(self, size, clock=time.monotonic, late_policy="drop",
                 keep_outputs=256, on_close=None):
        if size <= 0:
            raise ValueError("size must be positive")
        if late_policy not in ("drop", "count"):
            raise ValueError("late_policy must be 'drop' or 'count'")
        self._size = float(size)
        self._clock = clock
        self._late_policy = late_policy
        self._on_close = on_close
        self._lock = threading.Lock()
        # 任意时刻至多一个开口窗口：end > watermark 的对齐窗口唯一
        self._open_start = None
        self._open_total = 0.0
        self._watermark = None
        self._outputs = deque(maxlen=keep_outputs)
        self._late_count = 0
        self._late_total = 0.0
        self._last_arrival = None

    def _window_start(self, ts):
        k = math.floor(ts / self._size)
        # 浮点误差：ts 落在右边界上时归到右侧窗口
        if (k + 1) * self._size - ts <= 1e-9 * self._size:
            k += 1
        return k * self._size

    def _close_due(self):
        if self._open_start is None:
            return
        if self._open_start + self._size <= self._watermark:
            record = ClosedWindow(self._open_start,
                                  self._open_start + self._size,
                                  self._open_total)
            self._outputs.append(record)
            if self._on_close is not None:
                self._on_close(record)
            self._open_start = None
            self._open_total = 0.0

    def add(self, ts, v=1):
        """记一个事件，返回其所在窗口的累计和；被判迟到时返回 None。

        水位线取历史最大事件时间，只增不减；窗口随水位线推进关闭。
        """
        with self._lock:
            self._last_arrival = self._clock()
            if self._watermark is None or ts > self._watermark:
                self._watermark = ts
            self._close_due()
            start = self._window_start(ts)
            if start + self._size <= self._watermark:
                self._late_count += 1
                if self._late_policy == "count":
                    self._late_total += v
                return None
            if start != self._open_start:
                self._open_start = start
                self._open_total = 0.0
            self._open_total += v
            return self._open_total

    def window_total(self):
        """当前开口窗口（最近一个窗口）的计数和，无事件时为 0。"""
        with self._lock:
            return self._open_total

    def current_window(self):
        """当前开口窗口区间 (start, end)，无事件时返回 None。"""
        with self._lock:
            if self._open_start is None:
                return None
            return (self._open_start, self._open_start + self._size)

    def watermark(self):
        """当前水位线（历史最大事件时间），无事件时返回 None。"""
        with self._lock:
            return self._watermark

    def outputs(self):
        """已关闭窗口的产出记录，按窗口起点升序，最老的可能已过期。"""
        with self._lock:
            return list(self._outputs)

    def late_count(self):
        """被判迟到的事件条数（两种策略都计）。"""
        with self._lock:
            return self._late_count

    def late_total(self):
        """late_policy 为 "count" 时迟到事件的计数和，否则恒为 0。"""
        with self._lock:
            return self._late_total

    def last_arrival(self):
        """最近一次 add 的到达时刻，没有事件时返回 None。"""
        with self._lock:
            return self._last_arrival

    def merge(self, start_a, start_b):
        """合并两条相邻已关闭窗口产出，返回合并后的 ClosedWindow。

        仅当两条产出都还在缓冲内（未过期）且时间连续
        （a.end == b.start）时允许，否则抛 ValueError。
        """
        with self._lock:
            idx_a = idx_b = None
            for i, rec in enumerate(self._outputs):
                if rec.start == start_a:
                    idx_a = i
                if rec.start == start_b:
                    idx_b = i
            if idx_a is None or idx_b is None:
                raise ValueError("closed window not in buffer "
                                 "(expired or never closed)")
            rec_a, rec_b = self._outputs[idx_a], self._outputs[idx_b]
            if rec_a.end != rec_b.start:
                raise ValueError("windows are not contiguous")
            merged = ClosedWindow(rec_a.start, rec_b.end,
                                  rec_a.total + rec_b.total)
            for i in sorted((idx_a, idx_b), reverse=True):
                del self._outputs[i]
            self._outputs.insert(min(idx_a, idx_b), merged)
            return merged


class MultiWindowCounter:
    """同一份事件流并行维护多个长度窗口，各自独立淘汰。"""

    def __init__(self, sizes, clock=time.monotonic, late_policy="drop",
                 keep_outputs=256):
        sizes = list(sizes)
        if not sizes:
            raise ValueError("sizes must not be empty")
        self._windows = {
            s: WindowedCounter(s, clock=clock, late_policy=late_policy,
                               keep_outputs=keep_outputs)
            for s in sizes
        }

    def add(self, ts, v=1):
        """把事件写入全部窗口，返回 {size: 各窗口累计和或 None}。"""
        return {s: w.add(ts, v) for s, w in self._windows.items()}

    def window(self, size):
        """取指定长度的子窗口计数器。"""
        return self._windows[size]

    def totals(self):
        """各窗口当前开口窗口的计数和，{size: total}。"""
        return {s: w.window_total() for s, w in self._windows.items()}
