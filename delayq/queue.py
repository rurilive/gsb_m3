"""延时队列：任务按到期时间出队，heapq 实现，供调度侧消费。"""
import heapq
import itertools
import threading
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock


class _Entry:

    __slots__ = ("due", "task", "key", "cancelled")

    def __init__(self, due: float, task: Callable[[], Any], key: Optional[str]):
        self.due = due
        self.task = task
        self.key = key
        self.cancelled = False


class DelayedQueue:
    """按到期时间出队的延时队列。

    - add(task, delay, key=None)：delay 秒后到期；key 相同的重复提交
      以最后一次为准，旧条目作废，不会被再次执行
    - pop_ready()：弹出一个已到期（due <= 当前时刻）的任务并返回；
      同一时刻到期的任务按提交顺序；没有到期任务时返回 None
    - peek()：距最近到期任务的等待秒数，消费端按它睡眠后再轮询；
      队列为空返回 None
    """

    def __init__(self, clock: Optional[Clock] = None):
        self._clock = clock if clock is not None else SystemClock()
        self._heap = []
        self._seq = itertools.count()
        self._keyed = {}
        self._stale = 0
        self._lock = threading.Lock()

    def add(self, task: Callable[[], Any], delay: float, key: Optional[str] = None) -> None:
        """提交任务，delay 秒后到期。"""
        if delay < 0:
            raise ValueError("delay 不能为负")
        with self._lock:
            due = self._clock.monotonic() + delay
            entry = _Entry(due, task, key)
            if key is not None:
                old = self._keyed.get(key)
                if old is not None:
                    old.cancelled = True
                    self._stale += 1
                self._keyed[key] = entry
            heapq.heappush(self._heap, (due, next(self._seq), entry))

    def _purge_cancelled(self) -> None:
        """丢弃堆顶已作废的条目（调用方须持锁）。"""
        while self._heap and self._heap[0][2].cancelled:
            heapq.heappop(self._heap)
            self._stale -= 1

    def pop_ready(self) -> Optional[Callable[[], Any]]:
        """弹出一个已到期的任务；没有到期任务时返回 None。"""
        with self._lock:
            self._purge_cancelled()
            if not self._heap or self._heap[0][0] > self._clock.monotonic():
                return None
            _, _, entry = heapq.heappop(self._heap)
            if entry.key is not None and self._keyed.get(entry.key) is entry:
                del self._keyed[entry.key]
            return entry.task

    def peek(self) -> Optional[float]:
        """距最近到期任务的等待秒数；队列为空返回 None。"""
        with self._lock:
            self._purge_cancelled()
            if not self._heap:
                return None
            return max(0.0, self._heap[0][0] - self._clock.monotonic())

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap) - self._stale
