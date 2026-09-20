"""截止时间：把相对预算换算成绝对到期时刻，并判断是否已经耗尽。"""
from typing import Optional

from .clock import Clock, SystemClock


class Deadline:
    """一次调用的截止时刻。

    预算为负按 0 处理，即立刻到期。
    """

    def __init__(self, budget: float, clock: Optional[Clock] = None):
        self._clock = clock if clock is not None else SystemClock()
        # 记录到期时刻：现在 + 预算。必须用单调钟，墙钟会被校时拨动。
        self._expires_at = self._clock.monotonic() + max(0.0, budget)

    def remaining(self) -> float:
        """距到期还剩多少秒，已过期则为负数。"""
        return self._expires_at - self._clock.monotonic()

    def expired(self) -> bool:
        """预算是否已经耗尽。"""
        return self.remaining() <= 0.0
