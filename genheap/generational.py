"""分代标记清除堆。

在 ObjectHeap 的记账之上把对象分成年轻代和老年代：

- 新对象先进年轻代，连续 survive ``promote_after`` 轮回收后晋升老年代；
- minor_collect 只从年轻代根和记录集出发，标记过程绝不走进老年代，
  扫描量是年轻代的常数倍，跟老年代大小无关；
- 老年代对象新指向年轻代对象的写入由写屏障记账（store 自带），
  记账按“源对象”折叠，反复改引用不会让记录集无界膨胀；
- major_collect 全堆标记清除，顺手重建记录集；老年代只在
  major（或 collect 攒够阈值触发的 major）时才整体回收。

回收期间与 ObjectHeap 同一条规矩：待收名单按本轮开始时的快照定，
钩子里 alloc 不影响本轮结果，动根下一轮才生效，递归回收抛
CollectionError。
"""

from genheap.errors import BarrierError, CollectionError
from genheap.heap import ObjectHeap
from genheap.mark import trace

YOUNG = "young"
OLD = "old"


class GenerationalHeap(ObjectHeap):
    """年轻代 + 老年代的标记清除堆。

    ``promote_after`` 是对象晋升前要连续 survive 的回收轮数（minor 和
    major 都算一轮）；``major_threshold`` 非 None 时，collect 会在
    老年代自上一轮 major 后新增够这么多个对象时自动升级成 major，
    否则做 minor；``verify=True`` 时每轮 minor 后复核写屏障记账，
    漏记屏障会抛 BarrierError（测试与排障用，生产别开）。
    """

    def __init__(
            self,
            on_free=None,
            promote_after=2,
            major_threshold=None,
            verify=False,
    ):
        if not isinstance(promote_after, int) or promote_after < 1:
            raise ValueError("promote_after must be a positive int")
        if major_threshold is not None and (
                not isinstance(major_threshold, int)
                or major_threshold < 1):
            raise ValueError("major_threshold must be a positive int or None")
        super().__init__(on_free=on_free)
        self._promote_after = promote_after
        self._major_threshold = major_threshold
        self._verify = verify
        self._old = set()
        self._young = set()
        self._young_root_set = set()
        self._age = {}
        self._remembered = set()
        self._minor_collections = 0
        self._major_collections = 0
        self._promotions = 0
        self._young_scanned = 0
        self._old_scanned = 0
        self._old_at_last_major = 0

    # ---- 分配与分代查询 ----

    def alloc(self, kind="object", payload=None):
        oid = super().alloc(kind, payload)
        self._young.add(oid)
        self._age[oid] = 0
        return oid

    def generation(self, oid):
        """对象所在代：YOUNG 或 OLD。"""
        self._cell(oid)
        return OLD if oid in self._old else YOUNG

    def add_root(self, oid):
        added = super().add_root(oid)
        if added and oid not in self._old:
            self._young_root_set.add(oid)
        return added

    def drop_root(self, oid):
        super().drop_root(oid)
        self._young_root_set.discard(oid)

    def generations(self):
        """当前各代规模：{"young", "old"}。"""
        return {"young": len(self._young), "old": len(self._old)}

    def remembered(self):
        """记录集当前记账的老年代 oid，升序。"""
        return tuple(sorted(self._remembered))

    # ---- 写屏障 ----

    def store(self, src, slot, dst):
        old = super().store(src, slot, dst)
        self._write_barrier(src)
        return old

    def _write_barrier(self, src):
        """老年代对象的每次写入后复核：它若指向年轻代就进记录集。

        记账按源对象折叠，一个老对象反复改引用在记录集里至多占一个
        位置，天然不随写入次数膨胀。
        """
        if src not in self._old:
            return
        if any(dst not in self._old for dst in self._cells[src].refs.values()):
            self._remembered.add(src)
        else:
            self._remembered.discard(src)

    # ---- 回收入口 ----

    def collect(self):
        """攒够老年代做 major，否则做 minor；返回对应轮次的报告。"""
        if self._collecting:
            raise CollectionError("collect already in progress")
        if self._major_threshold is not None and (
                len(self._old) - self._old_at_last_major
                >= self._major_threshold):
            return self.major_collect()
        return self.minor_collect()

    def minor_collect(self):
        """只回收年轻代，不走进老年代；返回本轮报告。"""
        if self._collecting:
            raise CollectionError("collect already in progress")
        self._collecting = True
        try:
            roots = self._young_root_seeds()
            marked, young_visited, old_seeds = _trace_young(
                self._cells, self._old, roots, self._remembered)
            doomed = [
                oid for oid in sorted(self._young) if oid not in marked
            ]
            freed = self._sweep(doomed)
            promoted = self._age_and_promote(marked)
            self._prune_remembered()
            self._minor_collections += 1
            self._young_scanned += young_visited
            self._old_scanned += old_seeds
            self._scanned += young_visited + old_seeds
            self._collections += 1
            self._fire_hooks(freed)
            if self._verify:
                self._verify_barrier()
        finally:
            self._collecting = False
        return {
            "kind": "minor",
            "marked": len(marked),
            "swept": len(freed),
            "promoted": promoted,
            "scanned": young_visited + old_seeds,
            "young_scanned": young_visited,
            "old_scanned": old_seeds,
        }

    def major_collect(self):
        """全堆标记清除并重建记录集；返回本轮报告。"""
        if self._collecting:
            raise CollectionError("collect already in progress")
        self._collecting = True
        try:
            marked, scanned = trace(self._cells, self._roots)
            doomed = [oid for oid in sorted(self._cells) if oid not in marked]
            freed = self._sweep(doomed)
            promoted = self._age_and_promote(marked)
            self._remembered = {
                oid for oid in self._old
                if any(dst not in self._old
                       for dst in self._cells[oid].refs.values())
            }
            self._major_collections += 1
            self._old_at_last_major = len(self._old)
            self._scanned += scanned
            self._collections += 1
            self._fire_hooks(freed)
        finally:
            self._collecting = False
        return {
            "kind": "major",
            "marked": len(marked),
            "swept": len(freed),
            "promoted": promoted,
            "scanned": scanned,
        }

    # ---- 内部 ----

    def _young_root_seeds(self):
        return list(self._young_root_set)

    def _sweep(self, doomed):
        freed = []
        for oid in doomed:
            cell = self._cells.pop(oid)
            self._old.discard(oid)
            self._young.discard(oid)
            self._young_root_set.discard(oid)
            self._age.pop(oid, None)
            self._remembered.discard(oid)
            self._freed += 1
            freed.append((oid, cell.kind, cell.payload))
        return freed

    def _age_and_promote(self, survivors):
        promoted = []
        for oid in survivors:
            if oid in self._old:
                continue
            self._age[oid] += 1
            if self._age[oid] >= self._promote_after:
                self._old.add(oid)
                self._young.discard(oid)
                self._young_root_set.discard(oid)
                self._remembered.discard(oid)
                if any(dst not in self._old
                       for dst in self._cells[oid].refs.values()):
                    self._remembered.add(oid)
                promoted.append(oid)
        self._promotions += len(promoted)
        return promoted

    def _prune_remembered(self):
        self._remembered = {
            src for src in self._remembered
            if src in self._cells
            and any(dst not in self._old
                    for dst in self._cells[src].refs.values())
        }

    def _fire_hooks(self, freed):
        for oid, kind, payload in freed:
            if self._hook is not None:
                self._hook(self, oid, kind, payload)

    def verify_barrier(self):
        """复核写屏障记账：跨代引用必须有记录，记账必须真实。

        发现漏记（或悬空记账）抛 BarrierError，正常返回 None。
        """
        self._verify_barrier()

    def _verify_barrier(self):
        for src, cell in self._cells.items():
            for dst in cell.refs.values():
                if dst not in self._cells:
                    raise BarrierError(
                        "dangling ref %s->%s after collection" % (src, dst))
        for src in self._old:
            points_young = any(
                dst in self._cells and dst not in self._old
                for dst in self._cells[src].refs.values())
            if points_young and src not in self._remembered:
                raise BarrierError(
                    "missing write barrier: old oid=%s points young" % (src,))
        for src in self._remembered:
            if src not in self._cells or src not in self._old:
                raise BarrierError("stale remembered entry: oid=%s" % (src,))
            if not any(dst in self._cells and dst not in self._old
                       for dst in self._cells[src].refs.values()):
                raise BarrierError(
                    "bogus remembered entry: oid=%s" % (src,))

    def stats(self):
        stats = super().stats()
        stats.update({
            "young": len(self._young),
            "old": len(self._old),
            "minor_collections": self._minor_collections,
            "major_collections": self._major_collections,
            "promotions": self._promotions,
            "remembered": len(self._remembered),
            "young_scanned": self._young_scanned,
            "old_scanned": self._old_scanned,
        })
        return stats


def _trace_young(cells, old, young_roots, remembered):
    """只在年轻代内标记。

    种子 = 年轻代根 + 记录集老对象指向的年轻代对象。
    顺着出边走时一律不踏进老年代；记录集里的每个老对象至多检查一次，
    检查成本是常数，所以总扫描量只跟年轻代大小和记录集大小有关。
    返回 (marked, young_visited, old_seeds)。
    """
    marked = set()
    stack = []
    for oid in young_roots:
        if oid in cells and oid not in old and oid not in marked:
            marked.add(oid)
            stack.append(oid)
    old_seeds = 0
    for src in remembered:
        cell = cells.get(src)
        if cell is None:
            continue
        old_seeds += 1
        for dst in cell.refs.values():
            if dst in cells and dst not in old and dst not in marked:
                marked.add(dst)
                stack.append(dst)
    young_visited = 0
    while stack:
        oid = stack.pop()
        young_visited += 1
        for dst in cells[oid].refs.values():
            if dst in cells and dst not in old and dst not in marked:
                marked.add(dst)
                stack.append(dst)
    return marked, young_visited, old_seeds
