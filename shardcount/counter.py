"""单锁计数器：一把全局锁护住所有键的累加、读取与快照。

埋点管线里每个服务实例一个计数器，键是少数几个热点（请求总数、错误数、
队列深度）。读写都从同一把锁下面过，行为简单好推理，量小的时候够用。
纯标准库，clock 注入是为了记录最后变更时刻，测试可换成假时钟。
"""

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CounterStats:
    """计数器的一份只读快照。"""

    keys: int
    incrs: int
    snapshots: int
    last_change: float


class LockCounter:
    """一把全局锁护住全部键的计数器。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._values = {}
        self._incrs = 0
        self._snapshots = 0
        self._last_change = 0.0

    def incr(self, key, delta=1):
        """把 key 加上 delta，返回加完之后的值。delta 允许为负。"""
        if not isinstance(delta, int):
            raise TypeError("delta must be an int")
        with self._lock:
            value = self._values.get(key, 0) + delta
            self._values[key] = value
            self._incrs += 1
            self._last_change = self._clock()
        return value

    def get(self, key):
        """读 key 当前的值，没记过的键是 0。读也要过锁。"""
        with self._lock:
            return self._values.get(key, 0)

    def snapshot(self, key):
        """读出 key 当前的值并把该键清零，一步做完。

        没记过的键返回 0；清零之后 keys() 里不再有它。返回的是清零
        之前的值。
        """
        with self._lock:
            value = self._values.pop(key, 0)
            self._snapshots += 1
        return value

    def keys(self):
        """当前值非 0 的键，按名字排序返回。"""
        with self._lock:
            return sorted(k for k, v in self._values.items() if v != 0)

    def total(self):
        """所有键当前值之和。"""
        with self._lock:
            return sum(self._values.values())

    def stats(self):
        """本次开张以来的操作计数与最后变更时刻。"""
        with self._lock:
            return CounterStats(
                keys=len([v for v in self._values.values() if v != 0]),
                incrs=self._incrs,
                snapshots=self._snapshots,
                last_change=self._last_change,
            )
