"""最朴素的定容缓存，纯标准库。

现有能力（基线）：

- FifoCache(cap) 用一个固定容量的字典存键值，容量必须是正数，
  否则在构造处当场抛 ValueError；
- put(key, val) 写入并返回值，键不存在时若容量已满，先按插入先后
  淘汰最早插入的那一条，再把新键写进去；
- get(key) 取回对应值，键不存在返回 None；
- peek(key) 与 get 同义，返回对应值，键不存在返回 None，且不改变
  任何内部状态；
- keys() 返回当前全部键，顺序为插入先后；
- 条目只按插入先后淘汰，从来看访问的次数，也从不记录访问频次。

这一层只看插入顺序，冷热不分：先写进来的热键会被后写进来的冷键挤走。
以频次为核心的淘汰策略要在它之上另建实现。
"""


class FifoCache:
    """固定容量、按插入先后淘汰的缓存。"""

    def __init__(self, cap):
        if cap <= 0:
            raise ValueError("cap must be positive")
        self._cap = cap
        self._data = {}

    @property
    def cap(self):
        """容量。"""
        return self._cap

    def put(self, key, val):
        """写入并返回值，键不存在且已满时先淘汰最早插入的那一条。"""
        if key not in self._data and len(self._data) >= self._cap:
            self._evict_earliest()
        self._data[key] = val
        return val

    def _evict_earliest(self):
        """按插入先后淘汰最早插入的那一条。"""
        oldest = next(iter(self._data))
        del self._data[oldest]
        return oldest

    def get(self, key):
        """取回对应值，键不存在返回 None。"""
        return self._data.get(key)

    def peek(self, key):
        """与 get 同义，返回对应值且不改变任何内部状态。"""
        return self._data.get(key)

    def keys(self):
        """当前全部键，顺序为插入先后。"""
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data
