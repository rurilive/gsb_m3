"""截止时间：把相对预算换算成绝对到期时刻，并判断是否已经耗尽。

到期时刻锚定在单调钟上：单调钟只随真实时间单向前进，NTP 校时拨动
墙钟不会影响预算的计量。
"""
from typing import Optional

from .clock import Clock, SystemClock


class Deadline:
    """一次调用的截止时刻。

    预算为负按 0 处理，即立刻到期。
    """

    def __init__(self, budget: float, clock: Optional[Clock] = None):
        self._clock = clock if clock is not None else SystemClock()
        # 记录单调钟上的到期时刻：现在 + 预算。不能用墙钟 time()，
        # 否则校时回拨会让预算“变长”、前跳会让预算被提前掐断。
        self._expires_at = self._clock.monotonic() + max(0.0, budget)

    def remaining(self) -> float:
        """距到期还剩多少秒，已过期则为负数。"""
        return self._expires_at - self._clock.monotonic()

    def expired(self) -> bool:
        """预算是否已经耗尽。"""
        return self.remaining() <= 0.0
