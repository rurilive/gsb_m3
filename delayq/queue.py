"""延时队列：任务按到期时间出队，heapq 实现，供调度侧消费。"""
import heapq
import threading
from itertools import count
from typing import Any, Callable, Optional

from .clock import Clock, SystemClock


class _Entry:

    __slots__ = ("due", "seq", "task", "key")

    def __init__(self, due: float, seq: int, task: Callable[[], Any],
                 key: Optional[str]):
        self.due = due
        self.seq = seq
        self.task = task
        self.key = key


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
        self._keys = {}
        self._stale = 0
        self._seq = count()
        self._lock = threading.Lock()

    def add(self, task: Callable[[], Any], delay: float, key: Optional[str] = None) -> None:
        """提交任务，delay 秒后到期。"""
        if delay < 0:
            raise ValueError("delay 不能为负")
        with self._lock:
            due = self._clock.monotonic() + delay
            seq = next(self._seq)
            entry = _Entry(due, seq, task, key)
            if key is not None:
                old = self._keys.get(key)
                if old is not None:
                    self._stale += 1
                self._keys[key] = entry
            heapq.heappush(self._heap, (due, seq, entry))

    def pop_ready(self) -> Optional[Callable[[], Any]]:
        """弹出一个已到期的任务；没有到期任务时返回 None。"""
        with self._lock:
            now = self._clock.monotonic()
            while self._heap:
                _, _, entry = heapq.heappop(self._heap)
                if self._is_stale(entry):
                    self._stale -= 1
                    continue
                if entry.due > now:
                    heapq.heappush(self._heap, (entry.due, entry.seq, entry))
                    return None
                if entry.key is not None:
                    self._keys.pop(entry.key, None)
                return entry.task
            return None

    def peek(self) -> Optional[float]:
        """距最近到期任务的等待秒数；队列为空返回 None。"""
        with self._lock:
            entry = self._live_top()
            if entry is None:
                return None
            return max(0.0, entry.due - self._clock.monotonic())

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap) - self._stale

    def _live_top(self) -> Optional[_Entry]:
        """返回堆顶的有效条目，顺带丢弃失效旧条目（调用方需持锁）。"""
        while self._heap:
            entry = self._heap[0][2]
            if not self._is_stale(entry):
                return entry
            heapq.heappop(self._heap)
            self._stale -= 1
        return None

    def _is_stale(self, entry: _Entry) -> bool:
        """key 条目已被同 key 的新提交取代时即为失效（调用方需持锁）。"""
        return entry.key is not None and self._keys.get(entry.key) is not entry
