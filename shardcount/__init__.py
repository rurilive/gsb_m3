"""shardcount: 一个计数器小工具，纯标准库，无外部依赖。

当前实现只有一把全局锁的单计数器 ShardCounter：incr 与 get 都走
同一把锁，计数始终是一个整数。它没有分片、没有时间窗口、没有快照，
也拿不出上限与原子语义。
"""

from .counter import ShardCounter

__all__ = ["ShardCounter"]
