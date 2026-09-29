"""shardcount 的现有实现。

这里只有一个很朴素的单锁全局计数器：所有 incr 与 get 都抢同一把
互斥锁，计数就是一个整数。它没有分片、不看时间、拿不出窗口增量，
也没有快照与上限，因此并发一高，锁就成了瓶颈。
"""

import threading


class ShardCounter:
    """单锁全局计数器。

    只做三件确定的事：把一个整数加一或加若干、读出当前值、清零。
    所有操作共用一把锁，计数始终存放在单个整数字段里。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0

    def incr(self, delta=1):
        """把计数加上 delta。delta 必须是数值，布尔会被拒绝。"""
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise TypeError("delta must be a number")
        with self._lock:
            self._value += delta

    def get(self):
        """读出当前的计数值。"""
        with self._lock:
            return self._value

    def reset(self):
        """把计数清零，回到刚建立时的状态。"""
        with self._lock:
            self._value = 0
