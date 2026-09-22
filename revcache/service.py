"""把 ValueCache 架在 Backend 前面的读穿门面。

调用方只跟 CachedStore 打交道：读尽量由本地缓存满足，未命中回源并
把结果放进缓存；写先落到数据源，再让缓存里该 key 的副本失效。
"""

import threading

from revcache.backend import Backend, TransientError
from revcache.cache import ValueCache


class CachedStore:
    """带进程内缓存的读穿存储。

    read(key) 命中直接返回；key 不存在抛 KeyError，回源失败抛
    TransientError。write(key, value) 更新数据源并让缓存条目失效。
    delete(key) 两边一起删，返回 key 原先是否存在。
    """

    def __init__(self, backend, cache):
        self.backend = backend
        self.cache = cache
        self._lock = threading.Lock()
        self._reads = 0
        self._hits = 0
        self._misses = 0
        self._loads = 0
        self._load_errors = 0
        self._writes = 0
        self._deletes = 0

    def read(self, key):
        with self._lock:
            self._reads += 1
        try:
            value = self.cache.get(key)
        except KeyError:
            pass
        else:
            with self._lock:
                self._hits += 1
            return value
        with self._lock:
            self._misses += 1
        try:
            value = self.backend.get(key)
        except KeyError:
            raise
        except TransientError:
            with self._lock:
                self._load_errors += 1
            self.cache.put(key, None)
            raise
        with self._lock:
            self._loads += 1
        self.cache.put(key, value)
        return value

    def write(self, key, value):
        self.backend.set(key, value)
        self.cache.invalidate(key)
        with self._lock:
            self._writes += 1

    def delete(self, key):
        existed = self.backend.delete(key)
        self.cache.invalidate(key)
        with self._lock:
            self._deletes += 1
        return existed

    def stats(self):
        with self._lock:
            return {"reads": self._reads, "hits": self._hits,
                    "misses": self._misses, "loads": self._loads,
                    "load_errors": self._load_errors,
                    "writes": self._writes, "deletes": self._deletes}
