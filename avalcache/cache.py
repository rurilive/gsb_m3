"""进程内 TTL 缓存。

按 key 保存一段时间内有效的结果，时钟通过构造参数注入，测试里可以
换成手写的假时钟。命中、未命中、过期清除、回源次数统一在 stats() 里
汇总，条目数也一并给出。
"""

import random
import threading
import time


class TtlCache:
    """带过期时间的 key-value 缓存。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    jitter: put_many 批量写入时 TTL 的抖动比例，默认 0.1 表示在
        [ttl * (1 - jitter), ttl * (1 + jitter)] 区间内随机打散，避免
        同批 key 同一时刻集体过期；0 表示不抖动。单个 put 不抖动。
    rng: 随机数源，需要无随机性的场合可注入。
    """

    def __init__(self, clock=time.monotonic, jitter=0.1, rng=None):
        self._clock = clock
        self._jitter = jitter
        self._rng = rng if rng is not None else random.Random()
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

    def _jittered_ttl(self, ttl):
        """给批量写入的 ttl 加随机抖动，None（永不过期）原样返回。"""
        if ttl is None or not self._jitter:
            return ttl
        factor = 1.0 + self._rng.uniform(-self._jitter, self._jitter)
        return ttl * factor

    def put(self, key, value, ttl=None):
        """写入单个条目。ttl 为秒数，None 表示永不过期。

        覆盖已有 key 时按本次 ttl 重新计算到期时刻，不沿用旧值。
        """
        with self._lock:
            expires_at = self._expiry(ttl)
            self._entries[key] = (value, expires_at)

    def put_many(self, items, ttl=None):
        """批量写入，items 是 (key, value) 的可迭代对象。

        每个条目独立计算带抖动的到期时刻，避免同批 key 同时过期。
        """
        with self._lock:
            for key, value in items:
                expires_at = self._expiry(self._jittered_ttl(ttl))
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
        loaded = loader(key)
        self.put(key, loaded, ttl)
        return loaded

    def sweep(self):
        """主动清理过期条目，返回清掉的数量。

        清掉的条目计入 stats 的 expired，和读时顺手删除走同一口径。
        """
        now = self._clock()
        with self._lock:
            expired_keys = [
                key
                for key, (_, expires_at) in self._entries.items()
                if expires_at is not None and now >= expires_at
            ]
            for key in expired_keys:
                del self._entries[key]
            self._expired += len(expired_keys)
            return len(expired_keys)

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
