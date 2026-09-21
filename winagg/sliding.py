"""按事件时间推进的滑动窗口计数。

窗口只随事件时间推进（watermark = 已见最大事件时间），与到达时刻无关，
重放同一份历史数据得到完全相同的结果。窗口外的事件真实淘汰（物理删除），
被挤出窗口的滚动桶聚合成 ClosedWindow 产出，供离线补数捞取。纯标准库。
"""

import bisect
import threading
import time
from collections import namedtuple


class LateEventError(Exception):
    """事件时间早于窗口左边界，且 on_late="raise" 时抛出。"""


class ClosedWindow(namedtuple("ClosedWindow", "start end total count closed_at")):
    """一个已关闭滚动窗口的聚合产出。

    start/end 为事件时间区间 [start, end)，total/count 为窗口内聚合结果，
    closed_at 为关闭时刻的注入时钟读数（仅记录，不参与窗口推进）。
    """

    __slots__ = ()


class SlidingWindow:
    """最近 length 秒事件时间的计数窗口。

    on_late: 早于左边界事件的策略，"drop" 丢弃并记 late_count/late_total，
             "raise" 抛 LateEventError；两种都不会默默吞掉。
    closed_retention: 已关闭产出的保留时长（事件时间秒），None 表示一直
             保留到 drain_closed() 被调用。
    clock: 注入时钟，只用于给产出盖关闭时刻，不参与窗口推进。
    """

    def __init__(self, length, on_late="drop", closed_retention=None,
                 clock=time.monotonic):
        if length <= 0:
            raise ValueError("length 必须为正")
        if on_late not in ("drop", "raise"):
            raise ValueError("on_late 只能是 'drop' 或 'raise'")
        self._length = float(length)
        self._on_late = on_late
        self._closed_retention = closed_retention
        self._clock = clock
        self._lock = threading.Lock()
        self._events = []          # (ts, v) 按 ts 升序，窗口外即物理删除
        self._sum = 0.0
        self._watermark = None     # 已见最大事件时间
        self._late_count = 0
        self._late_total = 0.0
        self._buckets = {}         # 滚动桶起点 -> [total, count]（未关闭）
        self._closed = {}          # 起点 -> ClosedWindow（已关闭未过期）

    def add(self, ts, v=1):
        """记一个事件，返回当前窗口和；迟到被丢弃时返回 None。

        watermark 只在新到事件时间更大时前进；ts 落在窗口内的乱序事件
        照常计入，早于左边界按 on_late 策略处理。
        """
        with self._lock:
            if self._watermark is None or ts > self._watermark:
                self._watermark = ts
                self._advance()
            if ts < self._watermark - self._length:
                self._late_count += 1
                self._late_total += v
                if self._on_late == "raise":
                    raise LateEventError(
                        "事件时间 %r 早于窗口左边界 %r"
                        % (ts, self._watermark - self._length))
                return None
            bisect.insort(self._events, (ts, v))
            self._sum += v
            start = ts - (ts % self._length)
            bucket = self._buckets.setdefault(start, [0.0, 0])
            bucket[0] += v
            bucket[1] += 1
            return self._sum

    def _advance(self):
        """watermark 前进后：淘汰窗口外事件、关闭被挤出的桶、清过期产出。"""
        left = self._watermark - self._length
        cut = bisect.bisect_left(self._events, (left,))
        if cut:
            for _, v in self._events[:cut]:
                self._sum -= v
            del self._events[:cut]
        for start in [s for s in self._buckets if s + self._length <= left]:
            total, count = self._buckets.pop(start)
            self._closed[start] = ClosedWindow(start, start + self._length,
                                               total, count, self._clock())
        if self._closed_retention is not None:
            for start in [s for s, w in self._closed.items()
                          if self._watermark - w.end > self._closed_retention]:
                del self._closed[start]

    def sum(self):
        """当前窗口 [watermark - length, watermark] 内的计数和。"""
        with self._lock:
            return self._sum

    def count(self):
        """当前窗口内的事件条数。"""
        with self._lock:
            return len(self._events)

    def watermark(self):
        """当前事件时间水位线，没有事件时返回 None。"""
        with self._lock:
            return self._watermark

    def bounds(self):
        """当前窗口边界 (左, 右)，左闭右闭，没有事件时返回 None。"""
        with self._lock:
            if self._watermark is None:
                return None
            return (self._watermark - self._length, self._watermark)

    def late_count(self):
        """因早于左边界被丢弃/拒绝的事件条数。"""
        with self._lock:
            return self._late_count

    def late_total(self):
        """因早于左边界被丢弃/拒绝的计数增量之和。"""
        with self._lock:
            return self._late_total

    def closed(self):
        """当前保留的已关闭窗口产出，按起点升序。"""
        with self._lock:
            return [self._closed[s] for s in sorted(self._closed)]

    def drain_closed(self):
        """取出并清空全部已关闭窗口产出（离线补数捞取入口）。"""
        with self._lock:
            out = [self._closed[s] for s in sorted(self._closed)]
            self._closed.clear()
            return out

    def merge_closed(self, a_start, b_start):
        """合并两个相邻已关闭窗口，返回合并后的 ClosedWindow。

        仅当两者都未过期（仍在产出保留期内）且时间连续
        （a.end == b.start）时允许，否则抛 KeyError/ValueError。
        """
        with self._lock:
            a = self._closed.get(a_start)
            b = self._closed.get(b_start)
            if a is None or b is None:
                raise KeyError("已关闭窗口不存在或已过期: %r, %r"
                               % (a_start, b_start))
            if a.end != b.start:
                raise ValueError("只能合并时间连续的相邻窗口: %r 与 %r"
                                 % ((a.start, a.end), (b.start, b.end)))
            merged = ClosedWindow(a.start, b.end, a.total + b.total,
                                  a.count + b.count, b.closed_at)
            del self._closed[a_start]
            del self._closed[b_start]
            self._closed[merged.start] = merged
            return merged


class MultiWindow:
    """同一份事件流并行维护多个不同长度的 SlidingWindow，各自独立淘汰。"""

    def __init__(self, lengths, on_late="drop", closed_retention=None,
                 clock=time.monotonic):
        self._windows = {
            float(length): SlidingWindow(length, on_late=on_late,
                                         closed_retention=closed_retention,
                                         clock=clock)
            for length in lengths
        }

    def add(self, ts, v=1):
        """向全部窗口记一个事件，返回 {窗口长度: 各窗口和或 None}。"""
        return {length: w.add(ts, v) for length, w in self._windows.items()}

    def window(self, length):
        """取指定长度的 SlidingWindow。"""
        return self._windows[float(length)]

    def sum(self, length):
        """指定长度窗口的当前计数和。"""
        return self.window(length).sum()

    def count(self, length):
        """指定长度窗口内的事件条数。"""
        return self.window(length).count()

    def lengths(self):
        """并行的窗口长度，升序。"""
        return sorted(self._windows)
