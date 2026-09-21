"""把 ValueCache 架在 Backend 前面的读穿门面。

调用方只跟 CachedStore 打交道：读尽量由本地缓存满足，未命中回源并
把结果放进缓存；写先落到数据源，再让缓存里该 key 的副本失效。

并发约定：同一个 key 同时最多一趟回源（single-flight），并发 miss
的线程等在 flight 上共享同一个结果，回源期间不持任何锁，写和删不
会被慢读堵住。回源拿到的是 (值, 修订号)，回填前在条纹锁里核对修订
号仍是当前版本才写入，慢读因此盖不过期间发生的写或删；回源失败不
缓存，缓存写失败降级为直连数据源返回。
"""

import threading

from revcache.backend import Backend, TransientError
from revcache.cache import CacheError, ValueCache

_STRIPES = 64


class _Flight:
    """一趟进行中的回源，同 key 的并发读等在 event 上共享结果。"""

    __slots__ = ("event", "value", "error")

    def __init__(self):
        self.event = threading.Event()
        self.value = None
        self.error = None


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
        self._stripes = [threading.Lock() for _ in range(_STRIPES)]
        self._flights = {}
        self._reads = 0
        self._hits = 0
        self._misses = 0
        self._loads = 0
        self._load_errors = 0
        self._writes = 0
        self._deletes = 0

    def _stripe(self, key):
        return self._stripes[hash(key) % _STRIPES]

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
        with self._lock:
            flight = self._flights.get(key)
            if flight is None:
                flight = _Flight()
                self._flights[key] = flight
                leader = True
            else:
                leader = False
        if not leader:
            # 同 key 已有一趟回源在路上，等它回来共享结果。
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            return flight.value
        try:
            try:
                value, rev = self.backend.snapshot(key)
            except (KeyError, TransientError) as exc:
                if isinstance(exc, TransientError):
                    with self._lock:
                        self._load_errors += 1
                flight.error = exc
                raise
            with self._lock:
                self._loads += 1
            # 回源路上 key 可能已被改写或删除；修订号对不上就丢弃这
            # 份老快照，绝不把旧值回填进缓存。核对与回填跟
            # write/delete 的失效共用同一把条纹锁，判定和失效之间没
            # 有窗口。
            with self._stripe(key):
                if self.backend.revision(key) == rev:
                    try:
                        self.cache.put(key, value)
                    except CacheError:
                        pass  # 缓存写不进去时降级为直连，不影响读结果
            flight.value = value
            return value
        finally:
            # 先摘下 flight 再唤醒等待者，让后来的读自己发起新回源。
            with self._lock:
                self._flights.pop(key, None)
            flight.event.set()

    def write(self, key, value):
        self.backend.set(key, value)
        with self._stripe(key):
            self.cache.invalidate(key)
        with self._lock:
            self._writes += 1

    def delete(self, key):
        existed = self.backend.delete(key)
        with self._stripe(key):
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
