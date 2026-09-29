"""按访问频次淘汰的 LFU 缓存，纯标准库。

现有能力（基线）：

- 构造只要一个 capacity，容量是条目的最大条数；
- 每条记着值与累计访问次数，另有一个单调递增的访问序号记录最近一次使用；
- get 命中把次数加一并刷新序号，未命中只记一次未命中并返回 None；
- put 新键在容量满时先淘汰一条，淘汰取次数最小者，次数相同取最久未使用者；
- put 已有键改值并把次数加一；
- peek 只取值，不动次数也不动统计；
- stats 给出容量、条目数、命中、未命中与淘汰数。

当前没有过期、没有频次衰减，淘汰只在 put 新键时发生。
"""

import time


class _Entry:
    """缓存条目：值、访问次数与最近使用序号。"""

    __slots__ = ("value", "freq", "recency")

    def __init__(self, value):
        self.value = value
        self.freq = 1
        self.recency = 0


class LFUCache:
    """按访问频次淘汰的缓存。

    capacity 是条目数上限；淘汰挑次数最小者，次数相同挑最久未使用者。
    """

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

    def _touch(self, entry):
        self._seq += 1
        entry.recency = self._seq

    def get(self, key):
        """命中返回值并把次数加一；未命中返回 None 并记一次未命中。"""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        entry.freq += 1
        self._touch(entry)
        self._hits += 1
        return entry.value

    def peek(self, key):
        """只取值，不改次数、不记统计；键不存在返回 None。"""
        entry = self._entries.get(key)
        return None if entry is None else entry.value

    def put(self, key, value):
        """写入键值。已有键改值并把次数加一；新键在满容量时先淘汰一条。"""
        entry = self._entries.get(key)
        if entry is not None:
            entry.value = value
            entry.freq += 1
            self._touch(entry)
            return
        if len(self._entries) >= self.capacity:
            self._evict_one()
        entry = _Entry(value)
        self._touch(entry)
        self._entries[key] = entry

    def _evict_one(self):
        """淘汰一条：次数最小的先出，次数相同取最近使用序号最小者。"""
        if not self._entries:
            return
        victim = min(
            self._entries,
            key=lambda k: (self._entries[k].freq, self._entries[k].recency),
        )
        del self._entries[victim]
        self._evicted += 1

    def __contains__(self, key):
        return key in self._entries

    def __len__(self):
        return len(self._entries)

    def keys(self):
        """当前条目键，按插入顺序。"""
        return list(self._entries)

    def stats(self):
        """统计快照，独立 dict。"""
        return {
            "capacity": self.capacity,
            "size": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "evicted": self._evicted,
        }
