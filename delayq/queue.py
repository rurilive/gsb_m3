"""延时队列：任务按到期时间出队，heapq 实现，供调度侧消费。"""
import heapq
import threading
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock


class _Entry:

    __slots__ = ("due", "seq", "task", "key", "cancelled")

    def __init__(self, due: float, seq: int, task: Callable[[], Any],
                 key: Optional[str]):
        self.due = due
        self.seq = seq
        self.task = task
        self.key = key
        self.cancelled = False

    def __lt__(self, other):
        if self.due != other.due:
            return self.due < other.due
        return self.seq < other.seq


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
        self._seq = 0
        self._active = {}  # key -> 当前生效的 _Entry
        self._live = 0     # 未到期且未作废的条目数（不含堆中的陈旧条目）

    def add(self, task: Callable[[], Any], delay: float, key: Optional[str] = None) -> None:
        """提交任务，delay 秒后到期。"""
        if delay < 0:
            raise ValueError("delay 不能为负")
        with self._lock:
            due = self._clock.monotonic() + delay
            if key is not None and key in self._active:
                self._active[key].cancelled = True
                self._live -= 1
            entry = _Entry(due, self._seq, task, key)
            self._seq += 1
            heapq.heappush(self._heap, entry)
            if key is not None:
                self._active[key] = entry
            self._live += 1

    def pop_ready(self) -> Optional[Callable[[], Any]]:
        """弹出一个已到期的任务；没有到期任务时返回 None。"""
        with self._lock:
            now = self._clock.monotonic()
            while self._heap:
                entry = self._heap[0]
                if entry.cancelled:
                    heapq.heappop(self._heap)
                    continue
                if entry.due > now:
                    return None
                heapq.heappop(self._heap)
                self._live -= 1
                if entry.key is not None and self._active.get(entry.key) is entry:
                    del self._active[entry.key]
                return entry.task
            return None

    def peek(self) -> Optional[float]:
        """距最近到期任务的等待秒数；队列为空返回 None。"""
        with self._lock:
            while self._heap and self._heap[0].cancelled:
                heapq.heappop(self._heap)
            if not self._heap:
                return None
            return max(0.0, self._heap[0].due - self._clock.monotonic())

    def __len__(self) -> int:
        with self._lock:
            return self._live
