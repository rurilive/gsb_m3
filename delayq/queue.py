"""延时队列：任务按到期时间出队，heapq 实现，供调度侧消费。"""
import heapq
import threading
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock


class _Entry:

    __slots__ = ("due", "task", "key")

    def __init__(self, due: float, task: Callable[[], Any], key: Optional[str]):
        self.due = due
        self.task = task
        self.key = key

    def __lt__(self, other):
        return self.due < other.due


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
        self._lock = threading.Lock()

    def add(self, task: Callable[[], Any], delay: float, key: Optional[str] = None) -> None:
        """提交任务，delay 秒后到期。"""
        if delay < 0:
            raise ValueError("delay 不能为负")
        with self._lock:
            due = self._clock.monotonic() + delay
            heapq.heappush(self._heap, (due, delay, _Entry(due, task, key)))

    def pop_ready(self) -> Optional[Callable[[], Any]]:
        """弹出一个已到期的任务；没有到期任务时返回 None。"""
        with self._lock:
            if not self._heap:
                return None
            _, _, entry = heapq.heappop(self._heap)
            return entry.task

    def peek(self) -> Optional[float]:
        """距最近到期任务的等待秒数；队列为空返回 None。"""
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0][0]

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)
