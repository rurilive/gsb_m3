"""并发哈希表：读写锁加扩容期分批迁移。

扩容期间同时挂着两张表：旧表 src 和新表 dst，旧表按桶号从 0 起逐个搬进 dst，
next_index 之前的桶已经搬完（槽位腾空），之后的桶还在 src。读写都按迁移进度
路由，所以任何时刻 get / items 都不重不漏：

- 已迁走的桶只剩 dst 有数据；未迁的桶只剩 src 有数据；
- 新写的键按 hash 落桶，桶已迁就写 dst，没迁就写 src；
- 删除按桶号找到唯一所在的表，删掉就没了，不会在后续搬桶时复活。

每个写操作（put / delete）在写锁里最多推进一批桶就返回，step_hook 在锁外
回调，压测拿它打点或注入慢动作也不会把停顿记进锁内临界区。一批搬完整轮就
在同一临界区里收尾对调，旧表随即脱钩释放，不进退役列表。搬桶用"先整桶取
出、成功再腾空、失败回滚"的方式，半路抛异常也不会留下半张坏表：这次写已经
落地，键照样读得到，下一个写继续把这轮扩容推完。
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
        self._src = HashMap(self._capacity, self._load_factor, auto_grow=False)
        self._dst = None          # 迁移目标表，没有扩容在进行时为 None
        self._next_index = 0      # 下一个待迁桶号；其之前的桶已腾空
        self._size = 0            # 逻辑条目数，src/dst 合起来不重不漏
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
        done = total = 0
        try:
            self._puts += 1
            prev = self._put_locked(key, value)
            if prev is None:
                self._size += 1
            self._maybe_begin_locked()
            done, total = self._drive_batch_locked()
        finally:
            self._rw.release_write()
        if total and self._step_hook is not None and done > 0:
            self._step_hook(done, total)
        self._note_pause(t0)
        return prev

    def _put_locked(self, key, value):
        if value is None:
            raise ValueError("value must not be None")
        if self._dst is not None:
            target = self._dst if self._src_bucket(key) < self._next_index else self._src
            return target.put(key, value)
        return self._src.put(key, value)

    def get(self, key, default=None):
        """读值，缺失返回 default。"""
        t0 = self._clock()
        with self._rw.read():
            self._gets += 1
            value = self._get_locked(key, default)
        self._note_pause(t0)
        return value

    def _get_locked(self, key, default):
        if self._dst is not None:
            if self._src_bucket(key) < self._next_index:
                return self._dst.get(key, default)
            return self._src.get(key, default)
        return self._src.get(key, default)

    def delete(self, key):
        """删除键，返回是否删掉了。"""
        t0 = self._clock()
        self._rw.acquire_write()
        done = total = 0
        try:
            self._deletes += 1
            removed = self._delete_locked(key)
            if removed:
                self._size -= 1
            done, total = self._drive_batch_locked()
        finally:
            self._rw.release_write()
        if total and self._step_hook is not None and done > 0:
            self._step_hook(done, total)
        self._note_pause(t0)
        return removed

    def _delete_locked(self, key):
        if self._dst is not None:
            table = self._dst if self._src_bucket(key) < self._next_index else self._src
            if table.delete(key):
                return True
            other = self._src if table is self._dst else self._dst
            return other.delete(key)
        return self._src.delete(key)

    def _src_bucket(self, key):
        """键在旧表里的桶号；迁移按这个桶号的进度路由。

        翻倍时 src 第 i 桶的键在 dst 里会劈进 i 和 i+C 两桶，但它们
        整批随 src 的第 i 桶一起迁走，所以路由看的是 src 桶号。
        """
        return hash(key) % self._src.capacity

    def __len__(self):
        with self._rw.read():
            return self._size

    def items(self):
        """全部 (key, value) 的快照。"""
        with self._rw.read():
            entries = list(self._src.items())
            if self._dst is not None:
                entries.extend(self._dst.items())
            return entries

    def stats(self):
        """计数与表状态的快照，返回独立 dict，调用方随便改。"""
        with self._rw.read():
            live = [self._src]
            if self._dst is not None:
                live.append(self._dst)
            entries = sum(len(bucket) for table in live for bucket in table.buckets)
            pending = 0 if self._dst is None else self._src.capacity - self._next_index
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
        """装载因子顶过阈值、且当前没有扩容在跑，就开一轮新扩容。"""
        if self._dst is None and self._size > self._src.capacity * self._load_factor:
            self._dst = HashMap(self._src.capacity * 2, self._load_factor,
                                auto_grow=False)
            self._next_index = 0

    def _drive_batch_locked(self):
        """在写锁里把当前扩容往前推一批桶；整轮搬完就当场收尾。

        返回 (已迁桶数, 本轮总桶数)，供锁外回调 step_hook。一次写调用
        至多推进一批，不连着开下一轮，保证单次停顿有上界。
        """
        if self._dst is None:
            return 0, 0
        total = self._src.capacity
        for _ in range(self._batch):
            if self._next_index >= total:
                break
            self._move_bucket_locked(self._next_index)
            self._next_index += 1
        done = self._next_index
        if done >= total:
            self._settle_locked()
        return done, total

    def _move_bucket_locked(self, index):
        """把 src 第 index 桶搬进 dst，成功才腾空 src 的槽位。

        先把整桶摘下来（之后 src 这个槽位就是空的），再逐个写 dst；
        中途抛异常就把还没进 dst 的条目原样塞回 src，已进 dst 的删掉，
        恢复成"这个桶还没迁"的状态，绝不留下 src/dst 各一半的局面。
        """
        bucket = self._src.buckets[index]
        staged = list(bucket)
        self._src.buckets[index] = []
        inserted = []
        try:
            for key, value in staged:
                self._dst.put(key, value)
                inserted.append((key, value))
        except BaseException:
            for key, _value in inserted:
                self._dst.delete(key)
            self._src.buckets[index] = staged
            raise
        self._migrated_buckets += 1

    def _settle_locked(self):
        """迁移收尾：dst 转正，src 脱钩交给 GC，不留退役表。"""
        self._src = self._dst
        self._dst = None
        self._next_index = 0
        self._capacity = self._src.capacity
        self._resizes += 1

    def _note_pause(self, t0):
        elapsed = (self._clock() - t0) * 1000.0
        if elapsed > self._max_pause_ms:
            self._max_pause_ms = elapsed
