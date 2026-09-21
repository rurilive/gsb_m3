"""本机时钟的最小抽象。

工具链里所有读表都从这里走：墙上钟读时刻，单调钟量间隔，sleep 让本机
时间前进。生产用 SystemSource 接内核时钟；演示与测试用 ManualSource，
时间完全由调用方拨动，还能模拟一次校时把墙钟往前拨或往回拨。
"""

import time


class TimeSource:
    """本机时钟的两个读法加一个前进动作。"""

    def wall(self):
        """墙上钟读数，会被校时拨动。"""
        raise NotImplementedError

    def monotonic(self):
        """单调钟读数，只朝前走，校时拨不动它。"""
        raise NotImplementedError

    def sleep(self, seconds):
        """让本机时间前进 seconds 秒。"""
        raise NotImplementedError


class SystemSource(TimeSource):
    """接内核时钟，生产口径。"""

    def wall(self):
        return time.time()

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)


class ManualSource(TimeSource):
    """手动时钟，演示与测试用，时间完全由调用方拨动。

    建机时墙钟与单调钟对齐在同一个零点：只给 wall 时单调钟跟它同起点，
    要造错位就显式传 monotonic。此后 sleep 让两个读法一起前进；
    step_wall 只拨墙钟，模拟一次校时；set_wall 把墙钟直接设到某个值。
    单调钟没有后退的口子。
    """

    def __init__(self, wall=1_700_000_000.0, monotonic=None):
        self._wall = float(wall)
        self._monotonic = float(wall if monotonic is None else monotonic)

    def wall(self):
        return self._wall

    def monotonic(self):
        return self._monotonic

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError("sleep 不接受负值")
        self._wall += float(seconds)
        self._monotonic += float(seconds)

    def step_wall(self, delta):
        """模拟一次校时：墙钟跳 delta 秒，单调钟原地不动。"""
        self._wall += float(delta)

    def set_wall(self, value):
        """把墙钟直接设到某个值。"""
        self._wall = float(value)
