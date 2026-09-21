"""引用计数对象容器。

活对象的记账都在这里：外部引用（create / retain / release）、
对象之间的强引用（link / unlink）、归零回收与销毁回调。
"""

from objlife.errors import LinkError, RefCountError, UnknownObject
from objlife.record import Record


class ObjectStore:
    """带销毁回调的引用计数容器。

    计数归零立刻回收，顺序固定：先摘掉记录，再回调
    on_destroy(store, oid, kind, payload)，最后摘除出边，
    出边摘除可能连锁触发下一批回收。回调里可以继续操作容器。
    """

    def __init__(self, on_destroy=None):
        self._records = {}
        self._hook = on_destroy
        self._next_oid = 1
        self._created = 0
        self._destroyed = 0

    # ---- 对象生命周期 ----

    def create(self, kind="object", payload=None):
        """新建对象并返回 oid，调用方手里这一份引用已经计上。"""
        oid = self._next_oid
        self._next_oid += 1
        self._created += 1
        self._records[oid] = Record(oid, kind, payload)
        return oid

    def retain(self, oid):
        """加一份外部引用，返回新的总引用数。"""
        rec = self._record(oid)
        rec.ext += 1
        rec.count += 1
        return rec.count

    def release(self, oid):
        """放掉一份外部引用，归零则当场回收。

        手里没有外部引用还来放，抛 RefCountError。
        """
        rec = self._record(oid)
        if rec.ext <= 0:
            raise RefCountError("release below zero: oid=%d" % oid)
        rec.ext -= 1
        rec.count -= 1
        if rec.count == 0:
            self._reap(oid)
        return rec.count

    # ---- 对象之间的强引用 ----

    def link(self, src, dst):
        """src 持有 dst 的强引用，返回 dst 的新总引用数。"""
        src_rec = self._record(src)
        if src == dst:
            raise LinkError("self link: oid=%d" % src)
        dst_rec = self._record(dst)
        if dst in src_rec.out_links:
            raise LinkError("duplicate link: %d -> %d" % (src, dst))
        src_rec.out_links.append(dst)
        dst_rec.count += 1
        return dst_rec.count

    def unlink(self, src, dst):
        """摘掉 src 到 dst 的边，dst 归零则当场回收。"""
        src_rec = self._record(src)
        if dst not in src_rec.out_links:
            raise LinkError("no such link: %d -> %d" % (src, dst))
        dst_rec = self._record(dst)
        src_rec.out_links.remove(dst)
        dst_rec.count -= 1
        if dst_rec.count == 0:
            self._reap(dst)
        return dst_rec.count

    # ---- 查询 ----

    def alive(self, oid):
        return oid in self._records

    def refcount(self, oid):
        """总引用数：外部引用加入边。"""
        return self._record(oid).count

    def retain_count(self, oid):
        """外部引用数。"""
        return self._record(oid).ext

    def kind(self, oid):
        return self._record(oid).kind

    def payload(self, oid):
        return self._record(oid).payload

    def out_links(self, oid):
        """出边快照，改它不影响容器。"""
        return list(self._record(oid).out_links)

    def ids(self):
        """活对象的 oid，升序。"""
        return sorted(self._records)

    def roots(self):
        """外部引用还没放光的对象，升序。"""
        return sorted(oid for oid, rec in self._records.items() if rec.ext > 0)

    def stats(self):
        return {
            "alive": len(self._records),
            "created": self._created,
            "destroyed": self._destroyed,
            "links": sum(len(rec.out_links) for rec in self._records.values()),
        }

    def set_hook(self, on_destroy):
        """换掉销毁回调，传 None 表示不要回调。"""
        self._hook = on_destroy

    # ---- 内部 ----

    def _record(self, oid):
        try:
            return self._records[oid]
        except KeyError:
            raise UnknownObject("no such object: oid=%r" % (oid,)) from None

    def _reap(self, oid):
        rec = self._records.pop(oid)
        self._destroyed += 1
        try:
            if self._hook is not None:
                self._hook(self, oid, rec.kind, rec.payload)
        finally:
            for dst in rec.out_links:
                target = self._records.get(dst)
                if target is None:
                    continue
                target.count -= 1
                if target.count == 0:
                    self._reap(dst)
