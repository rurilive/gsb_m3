"""时间源。

调度器不直接读 time.time，一律通过注入的时钟取当前时间。
线上用 SystemClock，测试和演示用 ManualClock 手动推进，不真的等待。
"""

import time


class Clock:
    """时钟接口：now() 返回当前时间，单位秒（float，unix 纪元）。"""

    def now(self):
        raise NotImplementedError


class SystemClock(Clock):
    """系统时钟。"""

    def now(self):
        return time.time()


class ManualClock(Clock):
    """手动时钟。

    advance 往前走，set 可以往前也可以往回拨。
    """

    def __init__(self, start=0.0):
        self._now = float(start)

    def now(self):
        return self._now

    def advance(self, seconds):
        """往前推 seconds 秒，返回新的当前时间。"""
        self._now += float(seconds)
        return self._now

    def set(self, t):
        """直接设为某个时刻，允许小于当前值。"""
        self._now = float(t)
        return self._now
