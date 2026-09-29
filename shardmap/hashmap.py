"""单锁哈希表。

全部读写共用一把锁与一张桶表，桶内用链表做链地址法。
接口覆盖 get、put、delete、size 与几个只读探查方法。
哈希值由构造参数 hash_fn 提供，缺省用内置 hash，时钟与随机源都可注入。
"""

import threading


class ConcurrentHashMap:
    """单锁哈希表：所有操作都走同一把可重入锁。"""

    DEFAULT_CAPACITY = 8

    def __init__(self, capacity=DEFAULT_CAPACITY, hash_fn=None, clock=None):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._hash = hash_fn or hash
        self._clock = clock
        self._lock = threading.RLock()
        self._buckets = [[] for _ in range(capacity)]
        self._size = 0

    @property
    def size(self):
        """当前键值对数。"""
        with self._lock:
            return self._size

    @property
    def depth(self):
        """口径：单锁实现下并行度恒为 1。"""
        return 1

    def get(self, key, default=None):
        """按键取值，不存在返回 default。"""
        with self._lock:
            for k, v in self._buckets[self._index(key)]:
                if k == key:
                    return v
        return default

    def put(self, key, value):
        """插入或覆盖 key。

        新键返回 True 并让 size 加一；覆盖已有键返回 False。
        """
        with self._lock:
            bucket = self._buckets[self._index(key)]
            for i, (k, _) in enumerate(bucket):
                if k == key:
                    bucket[i] = (key, value)
                    return False
            bucket.append((key, value))
            self._size += 1
            return True

    def delete(self, key):
        """删除 key，返回是否删到。"""
        with self._lock:
            bucket = self._buckets[self._index(key)]
            for i, (k, _) in enumerate(bucket):
                if k == key:
                    del bucket[i]
                    self._size -= 1
                    return True
        return False

    def contains(self, key):
        """键是否存在。"""
        marker = object()
        return self.get(key, marker) is not marker

    def keys(self):
        """当前全部键的快照列表。"""
        with self._lock:
            out = []
            for bucket in self._buckets:
                for k, _ in bucket:
                    out.append(k)
            return out

    def items(self):
        """当前全部键值对的快照列表。"""
        with self._lock:
            out = []
            for bucket in self._buckets:
                for item in bucket:
                    out.append(item)
            return out

    def _index(self, key):
        # 只在持锁时调用：把键散列到桶下标。
        return self._hash(key) % len(self._buckets)
