"""分片计数器：热点键摊到按线程分配的槽位，读不挡写、写不互等。

LockCounter 里所有线程挤同一把锁；ShardedCounter 给每个写线程发一个
私有槽（一个 dict），属主线程独占写入，靠 GIL 保证单条 dict 操作原子，
写路径没有任何锁，写线程之间永远互不相等。get/keys/total/stats 无锁
汇总各槽。

snapshot/sync 需要跨槽原子时，用 Dekker 式静默协议：静默方先立
_quiescing 标志，再等各槽 writing 标志落下；写线程先立自己槽的
writing 再看 _quiescing，发现静默就退出临界区到条件变量上等。双方
至少有一方能看到对方的标志，不会错过也不会死锁。

两种模式：

- "exact"（默认）：每次 incr 直接落槽。多线程压完与 LockCounter 严格
  相等。
- "fast"：正增量先攒在线程本地挂账，凑够 batch 个（或遇到非正增量）
  才落槽。get 只读已落槽部分：读可滞后（上界约为活跃写线程数 x
  (batch - 1) 个增量）但绝不超真值；sync() 或写线程收工（线程本地
  清理钩子）后精确，一条不丢。

incr 的返回值是本线程槽位里该键的新值：单线程下与 LockCounter 完全
一致；多线程下同键的全局汇总请用 get(key)。高吞吐场景下为返回值做
全局汇总会把写路径打回串行，那正是单锁基线的病根。

fast 模式的 stats().last_change 记的是最后一次落槽（flush）时刻：
还躺在挂账里的增量对外不可见，不算"已变更"。
"""

import threading
import time
import weakref

from shardcount.counter import CounterStats

EXACT = "exact"
FAST = "fast"
_MODES = (EXACT, FAST)

DEFAULT_BATCH = 64


class _Slot:
    """一个写线程的私有槽：已落槽的值、fast 模式挂账与静默协议标志。"""

    __slots__ = ("values", "pending", "writing", "ops", "incrs", "last_change")

    def __init__(self, buffered):
        self.values = {}
        self.pending = {} if buffered else None
        self.writing = False
        self.ops = 0
        self.incrs = 0
        self.last_change = 0.0


class _Janitor:
    """线程本地清理钩子：属主线程收工时把挂账落槽，一条不丢。"""

    __slots__ = ("_counter", "_slot")

    def __init__(self, counter, slot):
        self._counter = weakref.ref(counter)
        self._slot = slot

    def __del__(self):
        counter_ref = getattr(self, "_counter", None)
        if counter_ref is None:
            return
        counter = counter_ref()
        if counter is not None:
            try:
                counter.sync()
            except Exception:
                pass  # 解释器收尾阶段随它去


class ShardedCounter:
    """热点键按写线程摊槽的计数器；mode="exact"（默认）或 "fast"。

    batch: fast 模式的挂账批量，读滞后上界随它缩放；exact 模式忽略。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    __slots__ = (
        "_mode", "_batch", "_clock", "_slots", "_reg_lock", "_tls",
        "_quiescing", "_qlock", "_qcond", "_snapshots", "__weakref__",
    )

    def __init__(self, mode=EXACT, batch=DEFAULT_BATCH, clock=time.monotonic):
        if mode not in _MODES:
            raise ValueError("mode must be one of %r" % (_MODES,))
        if not isinstance(batch, int) or batch < 1:
            raise ValueError("batch must be a positive int")
        self._mode = mode
        self._batch = batch
        self._clock = clock
        self._slots = []
        self._reg_lock = threading.Lock()
        self._tls = threading.local()
        self._quiescing = False
        self._qlock = threading.Lock()       # 同一时刻只有一个静默区
        self._qcond = threading.Condition()  # 写线程等静默结束
        self._snapshots = 0

    def incr(self, key, delta=1):
        """把 key 加上 delta，返回本线程槽位里该键的新值。delta 允许为负。"""
        if not isinstance(delta, int):
            raise TypeError("delta must be an int")
        try:
            pending, values, slot = self._tls.cache
        except AttributeError:
            pending, values, slot = self._own_cache()
        while True:
            slot.writing = True
            if not self._quiescing:
                break
            slot.writing = False
            self._wait_quiesce()
        try:
            if pending is not None:
                value = self._incr_fast(slot, values, pending, key, delta)
            else:
                value = values.get(key, 0) + delta
                values[key] = value
                slot.incrs += 1
                slot.last_change = self._clock()
        finally:
            slot.writing = False
        return value

    def get(self, key):
        """读 key 当前的汇总值，无锁；fast 模式只算已落槽部分。"""
        total = 0
        for slot in self._slots:
            total += slot.values.get(key, 0)
        return total

    def snapshot(self, key):
        """读出 key 的汇总值并把该键清零，跨槽原子完成。

        fast 模式先把所有挂账落槽再取，等价于一次 sync + 取值清零。
        没记过的键返回 0；清零之后 keys() 里不再有它。
        """
        with self._qlock:
            self._begin_quiesce()
            try:
                if self._mode == FAST:
                    for slot in list(self._slots):
                        self._flush(slot)
                value = 0
                for slot in list(self._slots):
                    value += slot.values.pop(key, 0)
                self._snapshots += 1
            finally:
                self._end_quiesce()
        return value

    def sync(self):
        """fast 模式：把所有线程的挂账落槽，之后 get 精确；exact 模式是空操作。"""
        if self._mode != FAST:
            return
        with self._qlock:
            self._begin_quiesce()
            try:
                for slot in list(self._slots):
                    self._flush(slot)
            finally:
                self._end_quiesce()

    def keys(self):
        """当前值非 0 的键，按名字排序；fast 模式只算已落槽部分。"""
        return sorted(k for k, v in self._totals().items() if v != 0)

    def total(self):
        """所有键当前值之和；fast 模式只算已落槽部分。"""
        return sum(self._totals().values())

    def stats(self):
        """本次开张以来的操作计数与最后变更时刻。"""
        incrs = 0
        last_change = 0.0
        for slot in self._slots:
            incrs += slot.incrs
            if slot.last_change > last_change:
                last_change = slot.last_change
        return CounterStats(
            keys=len(self.keys()),
            incrs=incrs,
            snapshots=self._snapshots,
            last_change=last_change,
        )

    @property
    def slot_count(self):
        """已分配的槽位数（等于写过数据的线程数）。"""
        return len(self._slots)

    def slot_values(self, key):
        """key 在各槽上的分量，演示与排查用；fast 模式只算已落槽部分。"""
        return [slot.values.get(key, 0) for slot in self._slots]

    def _own_cache(self):
        cache = getattr(self._tls, "cache", None)
        if cache is None:
            slot = _Slot(buffered=self._mode == FAST)
            with self._reg_lock:
                self._slots.append(slot)
            cache = (slot.pending, slot.values, slot)
            self._tls.cache = cache
            if self._mode == FAST:
                self._tls.janitor = _Janitor(self, slot)
        return cache

    def _incr_fast(self, slot, values, pending, key, delta):
        slot.incrs += 1
        if delta > 0:
            value = pending.get(key, 0) + delta
            pending[key] = value
            slot.ops += 1
            if slot.ops >= self._batch:
                self._flush(slot)
                slot.last_change = self._clock()
                return values.get(key, 0)
            return values.get(key, 0) + value
        # 非正增量不进挂账：先落槽再直接改，保证 get 绝不超真值
        self._flush(slot)
        value = values.get(key, 0) + delta
        values[key] = value
        slot.last_change = self._clock()
        return value

    def _flush(self, slot):
        # 调用方已在写临界区内（属主线程）或静默区内（sync/snapshot）
        pending = slot.pending
        if pending:
            values = slot.values
            for k, d in pending.items():
                values[k] = values.get(k, 0) + d
            pending.clear()
        slot.ops = 0

    def _totals(self):
        totals = {}
        for slot in self._slots:
            for k, v in slot.values.copy().items():
                totals[k] = totals.get(k, 0) + v
        return totals

    def _begin_quiesce(self):
        self._quiescing = True
        # 在场写线程的临界区只有几条字节码，转瞬即出；让出 GIL 等它们
        while any(slot.writing for slot in self._slots):
            time.sleep(0)

    def _end_quiesce(self):
        with self._qcond:
            self._quiescing = False
            self._qcond.notify_all()

    def _wait_quiesce(self):
        with self._qcond:
            while self._quiescing:
                self._qcond.wait()
