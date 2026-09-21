"""虚拟时钟：周期推进、超时判断都靠它，测试里不碰真实时间。"""


class SimClock:
    """可手动推进的单调时钟，单位秒。"""

    def __init__(self, start=0.0):
        if start < 0:
            raise ValueError("start must be non-negative")
        self._now = float(start)

    @property
    def now(self):
        """当前时刻。"""
        return self._now

    def advance(self, dt):
        """向前推进 dt 秒，返回推进后的时刻。dt 必须为正。"""
        if dt <= 0:
            raise ValueError("dt must be positive")
        self._now += float(dt)
        return self._now
