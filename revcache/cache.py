"""revcache 的进程内读缓存。

ValueCache 就是一张带容量上限和 LRU 顺序的 key 到值的表，外加一组
计数器。它不认识数据源，存什么、什么时候删都由调用方决定。写操作
可以按需注入失败，方便演练降级路径。
"""

import threading
from collections import OrderedDict


class CacheError(Exception):
    """缓存层写不进去。"""


class ValueCache:
    """带容量上限的 LRU 映射。

    capacity=None 表示不限容量。get 未命中抛 KeyError，put 覆盖写，
    invalidate 删一条，所有方法线程安全。
    """

    def __init__(self, capacity=None):
        self._lock = threading.Lock()
        self._entries = OrderedDict()
        self._capacity = capacity
        self._puts = 0
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        self._evictions = 0
        self._write_errors = 0
        self._write_faults = 0

    def get(self, key):
        """返回缓存里的值，key 不在时抛 KeyError。"""
        with self._lock:
            try:
                value = self._entries.pop(key)
            except KeyError:
                self._misses += 1
                raise KeyError(key)
            self._entries[key] = value
            self._hits += 1
            return value

    def put(self, key, value):
        """存入 value，超过容量时淘汰最久未用的条目。

        注入了写故障时抛 CacheError。
        """
        with self._lock:
            if self._write_faults > 0:
                self._write_faults -= 1
                self._write_errors += 1
                raise CacheError(key)
            self._puts += 1
            self._entries.pop(key, None)
            self._entries[key] = value
            if self._capacity is not None:
                while len(self._entries) > self._capacity:
                    self._entries.popitem(last=False)
                    self._evictions += 1

    def invalidate(self, key):
        """删掉 key 的条目，返回是否真的删掉了。"""
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                self._invalidations += 1
                return True
            return False

    def inject_write_faults(self, count=1):
        """让接下来 count 次 put 抛 CacheError。"""
        with self._lock:
            self._write_faults += count

    def keys(self):
        """返回当前持有的 key，最久的在前。"""
        with self._lock:
            return list(self._entries)

    def items(self):
        """返回当前持有的 (key, 值)，最久的在前。"""
        with self._lock:
            return list(self._entries.items())

    def __len__(self):
        with self._lock:
            return len(self._entries)

    def __contains__(self, key):
        with self._lock:
            return key in self._entries

    def stats(self):
        """返回计数器快照。"""
        with self._lock:
            return {"puts": self._puts, "hits": self._hits,
                    "misses": self._misses,
                    "invalidations": self._invalidations,
                    "evictions": self._evictions,
                    "write_errors": self._write_errors}
