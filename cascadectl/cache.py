"""单层 LRU 缓存，纯标准库。

现有能力（基线）：

- LRUCache(capacity) 按条目数上限构造，容量小于一在构造处拒绝；
- get(key) 取回值，键在且没过期算命中返回 (True, value)，否则返回 (False, None)；
- put(key, value) 写入并返回值，键已存在则覆盖值并把该键提到最新；
- evict() 主动挤掉最久未使用的条目并返回键，缓存空时返回 None；
- peek(key) 只看不更新使用次序；
- keys() 按最近使用次序从早到晚列出全部键；
- stats() 给出容量、条目数、命中、未命中与淘汰数。

这一层是单层的，淘汰掉的条目直接消失，没有下级可降级，也没有回写队列，
没有分层命中口径。两级缓存要在它之上另建模块。
"""


class LRUCache:
    """条目数有上限的单层 LRU 缓存。"""

    def __init__(self, capacity):
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._entries = {}
        self._seq = 0
        self._hits = 0
        self._misses = 0
        self._evicted = 0

    def _touch(self, key):
        self._seq += 1
        self._entries[key]["recency"] = self._seq

    def _evict_one(self):
        if not self._entries:
            return None
        victim = min(self._entries, key=lambda k: self._entries[k]["recency"])
        del self._entries[victim]
        self._evicted += 1
        return victim

    def get(self, key):
        """取回值。命中返回 (True, value)，未命中返回 (False, None)。"""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return (False, None)
        self._touch(key)
        self._hits += 1
        return (True, entry["value"])

    def put(self, key, value):
        """写入并返回值，键已存在则覆盖并提出到最新。"""
        if key in self._entries:
            self._entries[key]["value"] = value
        else:
            if len(self._entries) >= self.capacity:
                self._evict_one()
            self._entries[key] = {"value": value, "recency": 0}
        self._touch(key)
        return value

    def evict(self):
        """主动挤掉最久未使用的条目并返回其键，缓存为空返回 None。"""
        return self._evict_one()

    def peek(self, key):
        """只看不更新使用次序，键不存在返回 None。"""
        entry = self._entries.get(key)
        if entry is None:
            return None
        return entry["value"]

    def keys(self):
        """全部键，按最近使用次序从早到晚。"""
        return sorted(self._entries, key=lambda k: self._entries[k]["recency"])

    def stats(self):
        """当前统计：容量、条目数、命中、未命中与淘汰数。"""
        return {
            "capacity": self.capacity,
            "size": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "evicted": self._evicted,
        }

    def __len__(self):
        return len(self._entries)

    def __contains__(self, key):
        return key in self._entries