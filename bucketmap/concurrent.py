"""并发哈希表：读写锁加扩容期分批迁移。

写入把装载因子顶过阈值时开一轮扩容：新开一张两倍桶数的表，把旧表的桶逐个搬过去，
搬完对调。迁移放在写操作里推进，每搬完一批放开一次写锁，让读线程和别的写线程有窗
口进来。step_hook 每搬完一批桶回调一次，压测拿它打点或注入慢动作。
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
        self._dst = None          # 迁移目标表，没有扩容在进行时为 None
        self._pending = None      # 待迁移桶的快照
        self._migrated = 0
        self._resizing = False
        self._retired = []        # 历轮退役下来的旧表
        self._size = 0
        self._puts = 0
        self._gets = 0
        self._deletes = 0
        self._resizes = 0
        self._migrated_buckets = 0
        self._max_pause_ms = 0.0

    # ---- 对外入口 ----

    def put(self, key, value):
        """写入，返回原值；写入后顺带把进行中的扩容往前推。"""
        t0 = self._clock()
        self._rw.acquire_write()
        try:
            self._puts += 1
            before = self._table.size
            prev = self._table.put(key, value)
            self._size += self._table.size - before
            self._maybe_begin_locked()
            self._drive_locked()
        finally:
            self._rw.release_write()
        self._note_pause(t0)
        return prev

    def get(self, key, default=None):
        """读值，缺失返回 default。"""
        t0 = self._clock()
        with self._rw.read():
            self._gets += 1
            value = self._table.get(key, default)
        self._note_pause(t0)
        return value

    def delete(self, key):
        """删除键，返回是否删掉了。"""
        t0 = self._clock()
        self._rw.acquire_write()
        try:
            self._deletes += 1
            removed = False
            if self._dst is not None and self._dst.delete(key):
                removed = True
            elif self._table.delete(key):
                removed = True
            if removed:
                self._size -= 1
        finally:
            self._rw.release_write()
        self._note_pause(t0)
        return removed

    def __len__(self):
        with self._rw.read():
            return self._size

    def items(self):
        """全部 (key, value) 的快照。"""
        with self._rw.read():
            entries = list(self._table.items())
            if self._dst is not None:
                entries.extend(self._dst.items())
            return entries

    def stats(self):
        """计数与表状态的快照，返回独立 dict，调用方随便改。"""
        with self._rw.read():
            live = [self._table]
            if self._dst is not None:
                live.append(self._dst)
            live.extend(self._retired)
            entries = sum(len(bucket) for table in live for bucket in table.buckets)
            pending = 0 if self._pending is None else len(self._pending) - self._migrated
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

    def _maybe_begin_locked(self):
        """装载因子顶过阈值就开一轮扩容。"""
        if self._resizing:
            return
        if self._table.size <= self._capacity * self._load_factor:
            return
        self._dst = HashMap(self._capacity * 2, self._load_factor, auto_grow=False)
        self._pending = list(self._table.buckets)
        self._migrated = 0
        self._resizing = True

    def _drive_locked(self):
        """把进行中的扩容往前推，每搬完一批放开一次写锁。"""
        while self._dst is not None:
            total = len(self._pending)
            for _ in range(self._batch):
                if self._migrated >= total:
                    break
                self._move_bucket(self._migrated)
                self._migrated += 1
            self._rw.release_write()
            self._resizing = False
            if self._step_hook is not None:
                self._step_hook(self._migrated, total)
            self._rw.acquire_write()
            self._resizing = True
            if self._dst is not None and self._migrated >= total:
                self._settle_locked()
                return

    def _move_bucket(self, index):
        """把待迁快照里的第 index 桶并进目标表，旧表的桶腾空。"""
        for key, value in self._pending[index]:
            self._dst.put(key, value)
        self._pending[index] = []
        self._table.buckets[index] = []
        self._migrated_buckets += 1

    def _settle_locked(self):
        """迁移收尾：对调新旧表，旧表挪进退役列表。"""
        old = self._table
        self._table = self._dst
        self._dst = None
        self._pending = None
        self._migrated = 0
        self._resizing = False
        self._capacity = self._table.capacity
        self._resizes += 1
        self._retired.append(old)

    def _note_pause(self, t0):
        elapsed = (self._clock() - t0) * 1000.0
        if elapsed > self._max_pause_ms:
            self._max_pause_ms = elapsed
