"""shardcount: 埋点管线里的进程内计数包。

LockCounter 用一把全局锁护住所有键的累加、读取与快照；Registry 按名字
发同一份计数器实例；reference 提供确定性压测计划与纯算术参考，用来对拍；
bench 量吞吐。纯标准库，无外部依赖。
"""

from shardcount.counter import CounterStats, LockCounter
from shardcount.reference import drive, expected_totals, make_plan
from shardcount.registry import Registry

__all__ = [
    "CounterStats",
    "LockCounter",
    "Registry",
    "drive",
    "expected_totals",
    "make_plan",
]
