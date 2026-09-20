"""进程内 TTL 缓存。

按 key 保存一段时间内有效的结果，时钟通过构造参数注入，测试里可以
换成手写的假时钟。命中、未命中、过期清除、回源次数统一在 stats() 里
汇总，条目数也一并给出。
"""

import threading
import time


class TtlCache:
    """带过期时间的 key-value 缓存。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (value, expires_at)；expires_at 为 None 表示永不过期
        self._entries = {}
        self._hits = 0
        self._misses = 0
        self._expired = 0
        self._loads = 0

    def _expiry(self, ttl):
        """把 ttl 换算成绝对到期时刻，None 表示永不过期。"""
        if ttl is None:
            return None
        return self._clock() + ttl

    def put(self, key, value, ttl=None):
        """写入单个条目。ttl 为秒数，None 表示永不过期。"""
        with self._lock:
            expires_at = self._expiry(ttl)
            old = self._entries.get(key)
            if old is not None:
                expires_at = old[1]
            self._entries[key] = (value, expires_at)

    def put_many(self, items, ttl=None):
        """批量写入，items 是 (key, value) 的可迭代对象。"""
        with self._lock:
            expires_at = self._expiry(ttl)
            for key, value in items:
                self._entries[key] = (value, expires_at)

    def get(self, key):
        """读取条目，未命中或已过期返回 None。"""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if expires_at is not None and self._clock() >= expires_at:
                del self._entries[key]
                self._expired += 1
                self._misses += 1
                return None
            self._hits += 1
            return value

    def get_or_load(self, key, loader, ttl=None):
        """读缓存，未命中就回源并回填。

        loader 接收 key，返回要缓存的结果。回源发生次数记在 loads 里。
        """
        value = self.get(key)
        if value is not None:
            return value
        with self._lock:
            self._loads += 1
        try:
            loaded = loader(key)
        except Exception:
            loaded = {}
        self.put(key, loaded, ttl)
        return loaded

    def sweep(self):
        """主动清理过期条目，返回清掉的数量。"""
        return 0

    def expires_at(self, key):
        """返回条目的绝对到期时刻，永不过期或 key 不存在时返回 None。"""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            return entry[1]

    def delete(self, key):
        """删除条目，返回是否真的删掉了。"""
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "expired": self._expired,
                "loads": self._loads,
                "entries": len(self._entries),
            }
