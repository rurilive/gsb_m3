"""shardmap: 进程内并发哈希表。

当前只提供单锁哈希表 ConcurrentHashMap，是分段锁改造前的基线。
"""

from shardmap.hashmap import ConcurrentHashMap

__all__ = ["ConcurrentHashMap"]