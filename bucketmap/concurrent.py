"""并发哈希表：读写锁加扩容期分批迁移。

写入把装载因子顶过阈值时开一轮扩容：新开一张两倍桶数的表，旧表的桶分批迁过去，
迁完对调，旧表直接退役释放。迁移摊在写操作里推进，每次写最多搬 batch 个桶，
单次写的停顿有界。step_hook 每迁完一个桶回调一次，压测拿它打点或注入慢动作。
"""

import time

from .rwlock import RWLock
from .table import HashMap


class ConcurrentMap:
    """读写锁保护的哈希表，读写语义与 HashMap 一致。

    capacity / load_factor：初始桶数与装载因子阈值。
    batch：每次写操作最多推进的桶数。
    clock：返回当前时刻的可调用对象，默认 time.perf_counter。
    step_hook(已迁桶数, 总桶数)：每迁完一个桶回调一次，回调别做重活。

    扩容期间的不变式：一个键要么只在旧表（还没迁走的桶里），要么只在新表，
    绝不两边同时存在；读、写、删都要同时看两张表。
    """

    def __init__(self, capacity=8, load_factor=0.75, batch=2,
                 clock=time.perf_counter, step_hook=None):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if load_factor <= 0:
            raise ValueError("load_factor must be > 0")
        if batch < 1:
            raise ValueError("batch must be >= 1")
        self._rw = RWLock()
        self._capacity = int(capacity)
        self._load_factor = float(load_factor)
        self._batch = int(batch)
        self._clock = clock
        self._step_hook = step_hook
        self._table = HashMap(self._capacity, self._load_factor, auto_grow=False)
        self._dst = None           # 迁移目标表，没有扩容在进行时为 None
        self._pending_total = 0    # 本轮扩容要迁的桶数
        self._migrated = 0         # 本轮已迁完的桶数
        self._size = 0
        self._puts = 0
        self._gets = 0
        self._deletes = 0
        self._resizes = 0
        self._migrated_buckets = 0
        self._max_pause_ms = 0.0

    # ---- 对外入口 ----

    def put(self, key, value):
        """写入，返回原值；写入后顺带把进行中的扩容往前推一批。"""
        if value is None:
            raise ValueError("value must not be None")
        t0 = self._clock()
        self._rw.acquire_write()
        callbacks = ()
        try:
            self._puts += 1
            if self._dst is None:
                prev = self._table.put(key, value)
            else:
                # 扩容中：键若在旧表先摘掉，统一写进新表，守住唯一副本不变式。
                prev = self._table.get(key)
                if prev is not None:
                    self._table.delete(key)
                else:
                    prev = self._dst.get(key)
                self._dst.put(key, value)
            if prev is None:
                self._size += 1
            callbacks = self._advance_locked()
        finally:
            self._rw.release_write()
        self._run_hook(callbacks)
        self._note_pause(t0)
        return prev

    def get(self, key, default=None):
        """读值，缺失返回 default；扩容中两张表都要看。"""
        t0 = self._clock()
        with self._rw.read():
            self._gets += 1
            value = self._table.get(key)
            if value is None and self._dst is not None:
                value = self._dst.get(key)
            if value is None:
                value = default
        self._note_pause(t0)
        return value

    def delete(self, key):
        """删除键，返回是否删掉了；扩容中两张表都要查。"""
        t0 = self._clock()
        self._rw.acquire_write()
        callbacks = ()
        try:
            self._deletes += 1
            removed = self._table.delete(key)
            if not removed and self._dst is not None:
                removed = self._dst.delete(key)
            if removed:
                self._size -= 1
            callbacks = self._advance_locked()
        finally:
            self._rw.release_write()
        self._run_hook(callbacks)
        self._note_pause(t0)
        return removed

    def __len__(self):
        with self._rw.read():
            return self._size

    def items(self):
        """全部 (key, value) 的快照；扩容期取两表并集，键不重复。"""
        with self._rw.read():
            entries = self._table.items()
            if self._dst is not None:
                entries.extend(self._dst.items())
            return entries

    def stats(self):
        """计数与表状态的快照，返回独立 dict，调用方随便改。"""
        with self._rw.read():
            live = [self._table]
            if self._dst is not None:
                live.append(self._dst)
            entries = sum(len(bucket) for table in live for bucket in table.buckets)
            pending = 0
            if self._dst is not None:
                pending = self._pending_total - self._migrated
            return {
                "puts": self._puts,
                "gets": self._gets,
                "deletes": self._deletes,
                "resizes": self._resizes,
                "migrated_buckets": self._migrated_buckets,
                "pending_buckets": pending,
                "max_pause_ms": self._max_pause_ms,
                "tables_live": len(live),
                "entries": entries,
                "size": self._size,
            }

    # ---- 扩容与迁移 ----

    def _advance_locked(self):
        """按需开新一轮扩容并推进一批，返回锁外要回调的 (done, total) 序列。

        迁移途中抛异常不许拖垮这次写：状态保持可续跑，后面的写接着推。
        """
        try:
            self._maybe_begin_locked()
            return self._drive_locked()
        except Exception:
            return ()

    def _maybe_begin_locked(self):
        """装载因子顶过阈值且没有扩容在跑，才开新一轮。"""
        if self._dst is not None:
            return
        if self._size <= self._capacity * self._load_factor:
            return
        self._dst = HashMap(self._capacity * 2, self._load_factor, auto_grow=False)
        self._pending_total = self._table.capacity
        self._migrated = 0

    def _drive_locked(self):
        """推进一批桶，迁完就收尾；返回本次迁完的 (done, total) 序列。"""
        if self._dst is None:
            return ()
        total = self._pending_total
        callbacks = []
        for _ in range(self._batch):
            if self._migrated >= total:
                break
            self._move_bucket(self._migrated)
            self._migrated += 1
            callbacks.append((self._migrated, total))
        if self._migrated >= total:
            self._settle_locked()
        return callbacks

    def _move_bucket(self, index):
        """把旧表第 index 桶并进目标表，旧槽位腾空。

        搬的是旧表现存的活桶，删过的键不会被搬回去；半路抛异常时旧桶还在，
        已进新表的条目下次重搬是幂等覆盖，状态可续跑。
        """
        entries = list(self._table.buckets[index])
        for key, value in entries:
            self._dst.put(key, value)
        self._table.buckets[index] = []
        self._migrated_buckets += 1

    def _settle_locked(self):
        """迁移收尾：对调新旧表，旧表直接丢弃，等垃圾回收。"""
        self._table = self._dst
        self._dst = None
        self._pending_total = 0
        self._migrated = 0
        self._capacity = self._table.capacity
        self._resizes += 1

    def _run_hook(self, callbacks):
        """锁外回调 step_hook，回调抛异常不影响表状态。"""
        if self._step_hook is None:
            return
        for done, total in callbacks:
            try:
                self._step_hook(done, total)
            except Exception:
                pass

    def _note_pause(self, t0):
        elapsed = (self._clock() - t0) * 1000.0
        if elapsed > self._max_pause_ms:
            self._max_pause_ms = elapsed
