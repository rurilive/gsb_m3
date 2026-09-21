"""引用计数对象容器。

活对象的记账都在这里：外部引用（create / retain / release）、
对象之间的强引用（link / unlink）、归零回收与销毁回调。
collect() 在此之上补一轮标记清除，专门收引用计数收不掉的环；
weak() 给的弱引用不计入引用数，对象死后自动置空。
"""
import threading

from objlife.errors import LinkError, RefCountError, UnknownObject
from objlife.record import Record


class WeakRef:
    """指向容器内对象的弱引用，不持有引用计数。

    对象还活着时 get() 返回 oid，被回收后 get() 返回 None。
    """

    __slots__ = ("_store", "_oid")

    def __init__(self, store, oid):
        self._store = store
        self._oid = oid

    def get(self):
        store = self._store
        with store._lock:
            oid = self._oid
            if oid is not None and oid in store._records:
                return oid
            return None

    def __repr__(self):
        return "WeakRef(%r)" % (self.get(),)


class _Sweep:
    """一轮清除的现场：待收集合、回调里冒出的救援种子与计数。"""

    __slots__ = ("pending", "seeds", "collected", "nulled")

    def __init__(self, pending):
        self.pending = pending
        self.seeds = []
        self.collected = 0
        self.nulled = 0


class ObjectStore:
    """带销毁回调的引用计数容器。

    计数归零立刻回收，顺序固定：先摘掉记录，再回调
    on_destroy(store, oid, kind, payload)，最后摘除出边，
    出边摘除可能连锁触发下一批回收。回调里可以继续操作容器。
    """

    def __init__(self, on_destroy=None):
        self._records = {}
        self._incoming = {}
        self._weaks = {}
        self._hook = on_destroy
        self._next_oid = 1
        self._created = 0
        self._destroyed = 0
        self._clean = True
        self._sweep = None
        self._lock = threading.RLock()

    # ---- 对象生命周期 ----

    def create(self, kind="object", payload=None):
        """新建对象并返回 oid，调用方手里这一份引用已经计上。"""
        with self._lock:
            oid = self._next_oid
            self._next_oid += 1
            self._created += 1
            self._records[oid] = Record(oid, kind, payload)
            self._incoming[oid] = set()
            return oid

    def retain(self, oid):
        """加一份外部引用，返回新的总引用数。"""
        with self._lock:
            rec = self._record(oid)
            rec.ext += 1
            rec.count += 1
            sweep = self._sweep
            if sweep is not None and oid in sweep.pending:
                sweep.seeds.append(oid)
            return rec.count

    def release(self, oid):
        """放掉一份外部引用，归零则当场回收。

        手里没有外部引用还来放，抛 RefCountError。
        """
        with self._lock:
            rec = self._record(oid)
            if rec.ext <= 0:
                raise RefCountError("release below zero: oid=%d" % oid)
            rec.ext -= 1
            rec.count -= 1
            if rec.count == 0:
                self._begin_reap(oid)
            else:
                self._clean = False
            return rec.count

    def collect(self):
        """标记清除一轮：收掉从 roots 不可达的整片对象。

        roots 是外部引用（ext > 0）的活对象。返回收掉的对象数
        与被置空的弱引用数 (collected, nulled)。

        清除逐个对象走归零回收的老路径，所以回调时机与顺序不变；
        回调里新加的引用会把待收对象救回，回调抛错时异常照抛，
        但容器记账保持一致、可以继续 collect 收敛。
        """
        with self._lock:
            if self._clean and self._sweep is None:
                return (0, 0)

            collected = 0
            nulled = 0
            nested = self._sweep is not None
            try:
                while True:
                    pending = self._mark()
                    if not pending:
                        self._clean = True
                        break
                    sweep = _Sweep(pending)
                    self._sweep = sweep
                    try:
                        self._sweep_once(sweep)
                    finally:
                        if self._sweep is sweep:
                            self._sweep = None
                    collected += sweep.collected
                    nulled += sweep.nulled
                    if sweep.collected == 0:
                        self._clean = True
                        break
            finally:
                if nested:
                    outer = self._sweep
                    if outer is not None:
                        outer.collected += collected
                        outer.nulled += nulled
            return (collected, nulled)

    def weak(self, oid):
        """给 oid 建一份弱引用，不计引用数，对象死后 get() 为 None。"""
        with self._lock:
            self._record(oid)
            ref = WeakRef(self, oid)
            self._weaks.setdefault(oid, []).append(ref)
            return ref

    # ---- 对象之间的强引用 ----

    def link(self, src, dst):
        """src 持有 dst 的强引用，返回 dst 的新总引用数。"""
        with self._lock:
            src_rec = self._record(src)
            if src == dst:
                raise LinkError("self link: oid=%d" % src)
            dst_rec = self._record(dst)
            if dst in src_rec.out_links:
                raise LinkError("duplicate link: %d -> %d" % (src, dst))
            src_rec.out_links.append(dst)
            dst_rec.count += 1
            self._incoming[dst].add(src)
            sweep = self._sweep
            if (sweep is not None and src not in sweep.pending
                    and dst in sweep.pending):
                sweep.seeds.append(dst)
            return dst_rec.count

    def unlink(self, src, dst):
        """摘掉 src 到 dst 的边，dst 归零则当场回收。"""
        with self._lock:
            src_rec = self._record(src)
            if dst not in src_rec.out_links:
                raise LinkError("no such link: %d -> %d" % (src, dst))
            dst_rec = self._record(dst)
            src_rec.out_links.remove(dst)
            dst_rec.count -= 1
            incoming = self._incoming.get(dst)
            if incoming is not None:
                incoming.discard(src)
            if dst_rec.count == 0:
                self._begin_reap(dst)
            else:
                self._clean = False
            return dst_rec.count

    # ---- 查询 ----

    def alive(self, oid):
        with self._lock:
            return oid in self._records

    def refcount(self, oid):
        """总引用数：外部引用加入边。"""
        with self._lock:
            return self._record(oid).count

    def retain_count(self, oid):
        """外部引用数。"""
        with self._lock:
            return self._record(oid).ext

    def kind(self, oid):
        with self._lock:
            return self._record(oid).kind

    def payload(self, oid):
        with self._lock:
            return self._record(oid).payload

    def out_links(self, oid):
        """出边快照，改它不影响容器。"""
        with self._lock:
            return list(self._record(oid).out_links)

    def ids(self):
        """活对象的 oid，升序。"""
        with self._lock:
            return sorted(self._records)

    def roots(self):
        """外部引用还没放光的对象，升序。"""
        with self._lock:
            return sorted(oid for oid, rec in self._records.items()
                          if rec.ext > 0)

    def stats(self):
        with self._lock:
            return {
                "alive": len(self._records),
                "created": self._created,
                "destroyed": self._destroyed,
                "links": sum(len(rec.out_links)
                             for rec in self._records.values()),
            }

    def set_hook(self, on_destroy):
        """换掉销毁回调，传 None 表示不要回调。"""
        with self._lock:
            self._hook = on_destroy

    # ---- 内部 ----

    def _record(self, oid):
        try:
            return self._records[oid]
        except KeyError:
            raise UnknownObject("no such object: oid=%r" % (oid,)) from None

    def _mark(self):
        """从 ext > 0 的根出发迭代标记，返回不可达（待收）对象集合。"""
        records = self._records
        pending = set(records)
        seen = set()
        stack = [oid for oid, rec in records.items() if rec.ext > 0]
        while stack:
            oid = stack.pop()
            if oid in seen:
                continue
            seen.add(oid)
            rec = records.get(oid)
            if rec is None:
                continue
            for dst in rec.out_links:
                if dst not in seen and dst in records:
                    stack.append(dst)
        pending.difference_update(seen)
        return pending

    def _sweep_once(self, sweep):
        """清除一轮待收对象，回调里的新引用触发救援，直到 pending 清空。"""
        while sweep.pending:
            while sweep.seeds:
                seed = sweep.seeds.pop()
                if seed in sweep.pending:
                    self._rescue(seed, sweep)
            if not sweep.pending:
                break
            oid = min(sweep.pending)
            sweep.pending.discard(oid)
            if not self._is_condemned(oid, sweep):
                self._rescue(oid, sweep)
                continue
            rec = self._records.get(oid)
            if rec is None:
                continue
            was_zero = rec.count == 0
            if was_zero:
                self._begin_reap(oid)
            else:
                # 环里的每个对象都被同片的入边顶着，计数到不了零；
                # 强摘一个，剩下的按归零的老链式路径依次走。
                self._drive_reap([self._pop_record(oid)])

    def _is_condemned(self, oid, sweep):
        """还够不够格当垃圾：count 只来自待收对象的入边才算。"""
        rec = self._records.get(oid)
        if rec is None or rec.ext > 0 or oid not in sweep.pending:
            return False
        indeg = sum(1 for src in self._incoming[oid] if src in sweep.pending)
        return rec.count == indeg

    def _rescue(self, seed, sweep):
        """回调把 seed 救回可达集，沿它和其它可达对象的出边整片救。"""
        stack = [seed]
        while stack:
            oid = stack.pop()
            if oid not in sweep.pending:
                continue
            sweep.pending.discard(oid)
            rec = self._records.get(oid)
            if rec is None:
                continue
            kept = []
            for dst in rec.out_links:
                if dst in self._records:
                    kept.append(dst)
                    if dst in sweep.pending:
                        stack.append(dst)
                else:
                    # 已死的出边是本轮早先收掉的，顺手清掉。
                    self._incoming[dst].discard(oid)
            if len(kept) != len(rec.out_links):
                rec.out_links = kept

    def _begin_reap(self, oid):
        """归零回收的入口，记账与老的 _reap 完全一致。"""
        self._drive_reap([self._pop_record(oid)])

    def _pop_record(self, oid):
        rec = self._records.pop(oid)
        self._destroyed += 1
        self._incoming.pop(oid, None)
        sweep = self._sweep
        if sweep is not None:
            sweep.nulled += self._null_weaks(oid)
        else:
            self._null_weaks(oid)
        return rec

    def _null_weaks(self, oid):
        refs = self._weaks.pop(oid, ())
        nulled = 0
        for ref in refs:
            ref._oid = None
            nulled += 1
        return nulled

    def _drive_reap(self, roots):
        """显式栈跑回收，逐对象保持「摘记录 → 回调 → 摘出边连锁」的顺序。

        语义与原来的递归 _reap 相同：深度优先、父节点的 hook 先跑，
        hook 抛错后该节点剩余出边照摘（在 finally 里），
        摘边引发的子回收异常会顶掉当前正在传播的异常。
        """
        stack = [(rec, None) for rec in roots]
        exc = None
        while stack:
            rec, it = stack[-1]
            if it is None:
                stack[-1] = (rec, 0)
                if self._hook is not None:
                    try:
                        self._hook(self, rec.oid, rec.kind, rec.payload)
                    except BaseException as error:  # noqa: BLE003
                        exc = error
                    if exc is not None:
                        stack.pop()
                        continue
                stack[-1] = (rec, iter(list(rec.out_links)))
                continue
            try:
                dst = next(it)
            except StopIteration:
                stack.pop()
                continue
            target = self._records.get(dst)
            if target is None:
                continue
            target.count -= 1
            incoming = self._incoming.get(dst)
            if incoming is not None:
                incoming.discard(rec.oid)
            if target.count == 0:
                child = self._pop_record(dst)
                if self._sweep is not None and dst in self._sweep.pending:
                    self._sweep.pending.discard(dst)
                    self._sweep.collected += 1
                stack.append((child, None))
                continue
            sweep = self._sweep
            if (sweep is not None and dst in sweep.pending
                    and not self._is_condemned(dst, sweep)):
                sweep.seeds.append(dst)
        if exc is not None:
            raise exc
