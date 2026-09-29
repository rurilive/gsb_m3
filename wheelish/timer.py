"""列表式定时器：注册定时任务，手动推进时钟，取走到期任务。

当前实现把待触发任务放在一个列表里线性扫描。功能正确但任务多时开销随
任务数线性增长，且取消了也只能从列表里逐个比对剔除。
"""

import time


class TimerHandle:
    """register() 返回的句柄，用它取消任务。"""

    __slots__ = ("key", "payload", "deadline", "cancelled", "_timer")

    def __init__(self, key, payload, deadline, timer):
        self.key = key
        self.payload = payload
        self.deadline = deadline
        self.cancelled = False
        self._timer = timer

    def cancel(self):
        return self._timer.cancel(self)

    def __repr__(self):
        state = "cancelled" if self.cancelled else "pending"
        return f"TimerHandle(key={self.key!r}, deadline={self.deadline!r}, {state})"


class ListTimer:
    """最简单的定时器：一个无序列表装全部待触发任务。

    - register(delay, payload=None, key=None)：挂一个 delay 秒后触发的任务，返回句柄
    - tick(now)：把时钟推进到 now，取走所有 deadline <= now 的到期任务
    - cancel(handle)：取消任务，已取消或已触发的返回 False
    - clock 可注入，默认 time.monotonic
    """

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._now = float(self._clock())
        self._tasks = []

    @property
    def now(self):
        return self._now

    @property
    def size(self):
        return len(self._tasks)

    def register(self, delay, payload=None, key=None):
        if delay <= 0:
            raise ValueError("delay must be positive")
        deadline = self._now + delay
        handle = TimerHandle(key, payload, deadline, self)
        self._tasks.append(handle)
        return handle

    def tick(self, now):
        if now < self._now:
            raise ValueError("clock cannot move backwards")
        self._now = float(now)
        due = []
        rest = []
        for handle in self._tasks:
            if handle.cancelled:
                continue
            if handle.deadline <= self._now:
                due.append(handle)
            else:
                rest.append(handle)
        self._tasks = rest
        return due

    def cancel(self, handle):
        if handle.cancelled:
            return False
        if handle not in self._tasks:
            return False
        self._tasks.remove(handle)
        handle.cancelled = True
        return True