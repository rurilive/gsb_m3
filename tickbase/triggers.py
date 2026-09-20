"""触发规则。

每个触发器只需要回答一个问题：给定一个时刻，严格晚于它的第一个触发时刻是哪个。
"""

import math
import time


class Trigger:
    """触发器接口。"""

    def next_after(self, t):
        """返回严格晚于 t 的第一个触发时刻。"""
        raise NotImplementedError

    def catch_up(self, scheduled, now):
        """scheduled 是已经到点的计划时刻（scheduled <= now）。

        返回 (严格晚于 now 的下一个计划时刻, [scheduled, now] 区间内的计划点个数)。
        下一次计划时刻一律从 scheduled 沿网格往前推，与 now 无关，任务跑多久
        都不会带偏节奏。默认逐点往后数，子类有解析算法时可以覆盖。
        """
        count = 1
        cur = scheduled
        while True:
            nxt = self.next_after(cur)
            if nxt > now:
                return nxt, count
            count += 1
            cur = nxt


class IntervalTrigger(Trigger):
    """按固定间隔触发，注册后的第一次在注册时刻加一个间隔。"""

    def __init__(self, seconds):
        seconds = float(seconds)
        if seconds <= 0:
            raise ValueError("interval must be positive")
        self.seconds = seconds

    def next_after(self, t):
        return t + self.seconds

    def catch_up(self, scheduled, now):
        # 等距网格可以直接算，不必逐点迭代；加一点点 epsilon 抵消浮点误差，
        # 保证正好压在网格点上的 now 也算作到点。
        n = int(math.floor((now - scheduled) / self.seconds + 1e-9)) + 1
        return scheduled + n * self.seconds, n

    def __repr__(self):
        return f"IntervalTrigger({self.seconds:g}s)"


class DailyTrigger(Trigger):
    """按本地时间每天固定时刻触发。"""

    def __init__(self, hour, minute=0, second=0):
        if not 0 <= hour <= 23:
            raise ValueError("hour out of range")
        if not 0 <= minute <= 59:
            raise ValueError("minute out of range")
        if not 0 <= second <= 59:
            raise ValueError("second out of range")
        self.hour = hour
        self.minute = minute
        self.second = second

    def next_after(self, t):
        """t 之后就这个时刻的下一次；当天已经过了就顺延到明天。"""
        lt = time.localtime(t)
        for day_offset in (0, 1):
            cand = time.mktime(
                (
                    lt.tm_year,
                    lt.tm_mon,
                    lt.tm_mday + day_offset,
                    self.hour,
                    self.minute,
                    self.second,
                    0,
                    -1,
                    -1,
                )
            )
            if cand > t:
                return cand
        raise AssertionError("unreachable")

    def __repr__(self):
        return "DailyTrigger(%02d:%02d:%02d)" % (self.hour, self.minute, self.second)
