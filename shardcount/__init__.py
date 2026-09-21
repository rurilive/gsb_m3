"""shardcount: 埋点管线里的进程内计数包。

LockCounter 用一把全局锁护住所有键的累加、读取与快照；ShardedCounter
把热点键摊到按线程分配的槽位，写不互等、读不加写锁，exact 模式精确、
fast 模式有损快路；Registry 按名字发同一份计数器实例；reference 提供
确定性压测计划与纯算术参考，用来对拍；bench 量吞吐。纯标准库，无外部依赖。
"""

from shardcount.counter import CounterStats, LockCounter
from shardcount.reference import drive, expected_totals, make_plan
from shardcount.registry import Registry
from shardcount.sharded import ShardedCounter

__all__ = [
    "CounterStats",
    "LockCounter",
    "Registry",
    "ShardedCounter",
    "drive",
    "expected_totals",
    "make_plan",
]
