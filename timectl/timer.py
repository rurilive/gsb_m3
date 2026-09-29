"""朴素的循环触发定时器。

LoopTimer 把待触发任务放在一个列表里，每回 tick 都从头扫一遍，谁到点就
当场同步调用谁的回调。功能上够用，但只有「延迟一次」这一种语义：

- 没有周期任务，也没有暂停与恢复；
- 没有防抖与节流，短时间内的连打会原样放大成同样多次回调；
- 所有时间以注入时钟为准，调用方必须显式把时钟推进到某个时刻。
"""

import time


class LoopHandle:
    """register() 返回的句柄，用它取消任务。"""

    __slots__ = ("cb", "deadline", "cancelled", "_timer")

    def __init__(self, cb, deadline, timer):
        self.cb = cb
        self.deadline = deadline
        self.cancelled = False
        self._timer = timer

    def cancel(self):
        return self._timer.cancel(self)

    def __repr__(self):
        state = "cancelled" if self.cancelled else "pending"
        return f"LoopHandle(deadline={self.deadline!r}, {state})"


class LoopTimer:
    """最简单的定时器：一个列表装全部任务，到点同步回调。

    - LoopTimer(clock=None)：clock 可注入，默认 time.monotonic
    - register(delay, cb)：挂一个 delay 秒后同步调用 cb 的任务，返回句柄
    - tick(now)：把时钟推进到 now，按到期顺序同步调用回调，返回本轮触发列表
    - cancel(handle)：取消任务，已取消或已触发的返回 False
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

    def register(self, delay, cb):
        if delay <= 0:
            raise ValueError("delay must be positive")
        deadline = self._now + delay
        handle = LoopHandle(cb, deadline, self)
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
        for handle in due:
            if not handle.cancelled:
                handle.cb()
        return due

    def cancel(self, handle):
        if handle.cancelled:
            return False
        if handle not in self._tasks:
            return False
        self._tasks.remove(handle)
        handle.cancelled = True
        return True
