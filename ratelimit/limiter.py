"""固定窗口限流器。

请求按调用方 key 分组，每个 key 在每个时间窗口内最多放过 limit 次；
时钟可注入，方便做确定性的时间断言。当前只支持固定窗口一种策略。
"""

import threading


class FixedWindowLimiter:
    """固定窗口计数限流。

    limit: 每窗口允许的次数。
    window: 窗口宽度（秒）。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, limit, window, clock=None):
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window <= 0:
            raise ValueError("window must be > 0")
        self._limit = limit
        self._window = float(window)
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (窗口起点, 该窗口已用次数)
        self._state = {}

    def _now(self):
        return self._clock() if self._clock is not None else _monotonic()

    def allow(self, key, n=1):
        """尝试为 key 放行 n 次。

        返回本次实际放行的次数（0 <= 实际 <= n）：窗口内剩余额度不足时
        只放行剩余部分，额度为 0 时返回 0。
        """
        if n < 0:
            raise ValueError("n must not be negative")
        if n == 0:
            return 0
        now = self._now()
        with self._lock:
            start, used = self._state.get(key, (now, 0))
            if now - start >= self._window:
                start, used = now, 0
            room = self._limit - used
            granted = n if n <= room else max(room, 0)
            self._state[key] = (start, used + granted)
            return granted

    def remaining(self, key):
        """当前窗口内 key 还剩多少额度。"""
        now = self._now()
        with self._lock:
            start, used = self._state.get(key, (now, 0))
            if now - start >= self._window:
                return self._limit
            return max(self._limit - used, 0)


def _monotonic():
    import time
    return time.monotonic()
