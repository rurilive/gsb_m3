"""把 ValueCache 架在 Backend 前面的读穿门面。

调用方只跟 CachedStore 打交道：读尽量由本地缓存满足，未命中回源并
把结果放进缓存；写先落到数据源，再让缓存里该 key 的副本失效。

并发语义：

- 每个 key 有一个失效代际号，写和删在清缓存的同一把锁里推高它。
  回源前记下代际号，取回值后只有代际号没变才把结果放进缓存，
  所以卡在回源里的慢读不会把改前的旧值盖回缓存。
- 同一个 key 的并发未命中合并成一次回源，其余线程等这一次的结果，
  缓存被清空后不会出现几十路一起回源。
- 回源失败不往缓存里写；缓存自己写不进去时降级成直连，本次读到的
  值照样返回。
"""

import threading

from revcache.backend import Backend, TransientError
from revcache.cache import CacheError, ValueCache


class _LoadSlot:
    """一次进行中的回源，同 key 的后来者等它出结果，不再各回各的源。"""

    def __init__(self):
        self.done = threading.Event()
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
        self._generations = {}
        self._inflight = {}
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
            slot = self._inflight.get(key)
            if slot is None:
                slot = _LoadSlot()
                self._inflight[key] = slot
                leader = True
                generation = self._generations.get(key, 0)
            else:
                leader = False
        if not leader:
            slot.done.wait()
            if slot.error is not None:
                raise slot.error
            return slot.value
        try:
            try:
                value = self.backend.get(key)
            except KeyError as exc:
                slot.error = exc
                raise
            except TransientError as exc:
                slot.error = exc
                with self._lock:
                    self._load_errors += 1
                raise
            with self._lock:
                self._loads += 1
                if self._generations.get(key, 0) == generation:
                    try:
                        self.cache.put(key, value)
                    except CacheError:
                        pass
            slot.value = value
            return value
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            slot.done.set()

    def write(self, key, value):
        self.backend.set(key, value)
        with self._lock:
            self._generations[key] = self._generations.get(key, 0) + 1
            self.cache.invalidate(key)
            self._writes += 1

    def delete(self, key):
        existed = self.backend.delete(key)
        with self._lock:
            self._generations[key] = self._generations.get(key, 0) + 1
            self.cache.invalidate(key)
            self._deletes += 1
        return existed

    def stats(self):
        with self._lock:
            return {"reads": self._reads, "hits": self._hits,
                    "misses": self._misses, "loads": self._loads,
                    "load_errors": self._load_errors,
                    "writes": self._writes, "deletes": self._deletes}
