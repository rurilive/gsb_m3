"""标记清除对象堆。

分配、根集合、槽位读写都走这里。collect 是全堆标记清除：
从根集合出发能走到的对象留下，走不到的整片收掉，收掉的对象
逐个回调 on_free 钩子。
"""

from genheap.errors import CollectionError, RootError, SlotError, UnknownObject
from genheap.mark import trace, unmarked


class Cell:
    """堆里一个活对象的记账：种类、负载、出边。

    出边是槽位名到 oid 的映射，只保留还活着的对象；
    把槽位写回 None 就是删掉这条出边。
    """

    def __init__(self, oid, kind="object", payload=None):
        self.oid = oid
        self.kind = kind
        self.payload = payload
        self.refs = {}


class ObjectHeap:
    """纯标记清除的堆。

    对象靠根可达活着，就近回收的原则一条：不看引用计数，
    只看从根能不能走到。对象可以有指向自己的槽位，不算错。

    钩子 on_free(heap, oid, kind, payload) 在对象已经从堆里摘干净
    之后才回调，回调里 alive(oid) 为假，可以继续 alloc、动根；
    正在回收时再次调 collect 会抛 CollectionError。
    钩子抛出的异常原样往上传：已经收掉的算收掉，剩下的留到下一轮，
    堆本身必须还能继续用。
    """

    def __init__(self, on_free=None):
        self._cells = {}
        self._roots = set()
        self._hook = on_free
        self._next_oid = 1
        self._allocated = 0
        self._freed = 0
        self._collections = 0
        self._scanned = 0
        self._collecting = False

    # ---- 分配与查询 ----

    def alloc(self, kind="object", payload=None):
        """分配一个对象，返回 oid。新对象不在根集合里。"""
        oid = self._next_oid
        self._next_oid += 1
        self._cells[oid] = Cell(oid, kind, payload)
        self._allocated += 1
        return oid

    def alive(self, oid):
        """对象当前是否活着。"""
        return oid in self._cells

    def ids(self):
        """所有活着的 oid，升序。"""
        return tuple(sorted(self._cells))

    def kind(self, oid):
        """对象的种类。"""
        return self._cell(oid).kind

    def payload(self, oid):
        """对象的负载。"""
        return self._cell(oid).payload

    # ---- 根集合 ----

    def add_root(self, oid):
        """把一个活对象挂进根集合，重复挂返回 False。"""
        self._cell(oid)
        if oid in self._roots:
            return False
        self._roots.add(oid)
        return True

    def drop_root(self, oid):
        """把对象从根集合里摘掉，本来就不是根则抛 RootError。"""
        if oid not in self._roots:
            raise RootError("not a root: oid=%s" % (oid,))
        self._roots.discard(oid)

    def roots(self):
        """根集合，升序。"""
        return tuple(sorted(self._roots))

    # ---- 槽位读写 ----

    def store(self, src, slot, dst):
        """把 src 的 slot 槽位写成指向 dst，dst 为 None 表示清空。

        返回这个槽位原来的值（oid 或 None）。src 和 dst 都必须是
        活对象，允许 src 指向自己。
        """
        cell = self._cell(src)
        _check_slot(slot)
        if dst is None:
            return cell.refs.pop(slot, None)
        self._cell(dst)
        old = cell.refs.get(slot)
        cell.refs[slot] = dst
        return old

    def load(self, src, slot):
        """读 src 的 slot 槽位，没写过或已清空则为 None。"""
        cell = self._cell(src)
        _check_slot(slot)
        return cell.refs.get(slot)

    def slots(self, src):
        """src 上当前有值的槽位名，升序。"""
        return tuple(sorted(self._cell(src).refs))

    def refs(self, oid):
        """oid 直接指向的对象，去重升序。"""
        return tuple(sorted(set(self._cell(oid).refs.values())))

    # ---- 回收 ----

    def collect(self):
        """全堆标记清除，返回本轮的 {"marked", "swept", "scanned"}。"""
        if self._collecting:
            raise CollectionError("collect already in progress")
        self._collecting = True
        try:
            marked, scanned = trace(self._cells, self._roots)
            doomed = unmarked(self._cells, marked)
            freed = []
            for oid in doomed:
                cell = self._cells.pop(oid)
                self._freed += 1
                freed.append((oid, cell.kind, cell.payload))
            self._scanned += scanned
            self._collections += 1
            for oid, kind, payload in freed:
                if self._hook is not None:
                    self._hook(self, oid, kind, payload)
        finally:
            self._collecting = False
        return {"marked": len(marked), "swept": len(freed), "scanned": scanned}

    def stats(self):
        """堆的累计账目。"""
        return {
            "alive": len(self._cells),
            "allocated": self._allocated,
            "freed": self._freed,
            "collections": self._collections,
            "scanned": self._scanned,
            "roots": len(self._roots),
        }

    # ---- 内部 ----

    def _cell(self, oid):
        cell = self._cells.get(oid)
        if cell is None:
            raise UnknownObject("no such object: oid=%s" % (oid,))
        return cell


def _check_slot(slot):
    if not isinstance(slot, str) or not slot:
        raise SlotError("slot must be a non-empty string: %r" % (slot,))
