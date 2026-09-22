"""增量拓扑引擎。

IncrementalTopo 在 DiGraph 上维护一份可以复用的拓扑序。加边删边先记账，
查询时把积压的操作结算到序上，尽量只重排受影响的区间，而不是整图重算。
入度表 _indeg 是引擎自己的账本，结算和出队都以它为准。

判定基准是 reference.py 的全量实现：同层节点按加入先后出队，
序只跟当前图和节点加入顺序有关。
"""

import heapq

from topoflow.graph import DiGraph
from topoflow.reference import CycleError, reference_is_acyclic


# 单次删边最多顺带看一眼的后继节点数，看不过来就退化成整图重排
_EXTENT_CAP = 4096


class IncrementalTopo:
    """增量拓扑排序。

    增删入口：add_node / add_edge / remove_edge / add_edges / remove_edges，
    查询入口：order / is_acyclic / in_degree / rank / nodes / snapshot。
    remove_edge 删一条不存在的边返回 False；order 有环抛 CycleError。
    """

    def __init__(self):
        self._graph = DiGraph()
        self._seq = {}           # node -> 加入序号
        self._indeg = {}         # node -> 入度，引擎自己记的账
        self._order = []         # 最近一次排出的序
        self._pos = {}           # node -> 在序里的位置
        self._cyclic = False     # 环标记，清了才能继续排
        self._cycle_hint = None  # 记下封环的那条边，删掉它才清标记
        self._pending = []       # 自上次结算以来登记过的边
        self._dirty = False
        self._rebuild = True     # 要不要整图重排
        self._lo = None          # 需要重排的区间两端
        self._hi = None

    def add_node(self, node):
        """登记一个节点，已存在返回 False。"""
        if node in self._seq:
            return False
        self._graph.add_node(node)
        self._seq[node] = len(self._seq)
        self._indeg[node] = 0
        self._pos[node] = len(self._order)
        self._order.append(node)
        return True

    def add_edge(self, u, v):
        """加一条边，返回是否新加了边。"""
        self._ensure(u)
        self._ensure(v)
        self._graph.add_edge(u, v)
        self._indeg[v] = self._indeg.get(v, 0) + 1
        self._pending.append((u, v))
        self._touch_pair(u, v)
        return True

    def add_edges(self, pairs):
        """批量加边，导入工具的主入口。"""
        for u, v in pairs:
            self._ensure(u)
            self._ensure(v)
            if self._graph.add_edge(u, v):
                self._indeg[v] = self._indeg.get(v, 0) + 1
            self._pending.append((u, v))
            self._touch_pair(u, v)

    def remove_edge(self, u, v):
        """删一条边，返回是否真的删掉了。"""
        if not self._graph.has_edge(u, v):
            return False
        self._graph.remove_edge(u, v)
        self._indeg[v] = self._indeg.get(v, 0) - 1
        self._touch_removal(v)
        if self._cyclic and self._cycle_hint == (u, v):
            self._cyclic = False
            self._cycle_hint = None
        return True

    def remove_edges(self, pairs):
        """批量删边，回放删边日志走这个入口。"""
        pairs = list(pairs)
        for u, v in pairs:
            self._graph.remove_edge(u, v)
            if v in self._indeg:
                self._indeg[v] -= 1
            if v in self._pos:
                self._touch_removal(v)

    # ---- 记账与结算 ----------------------------------------------------

    def _ensure(self, node):
        if node not in self._seq:
            self.add_node(node)

    def _touch_pair(self, u, v):
        """加边记脏：v 至少要挪到 u 后面，中间这一段都得重排。"""
        self._dirty = True
        pu, pv = self._pos.get(u), self._pos.get(v)
        if pu is None or pv is None:
            self._rebuild = True
            return
        lo, hi = min(pu, pv), max(pu, pv)
        if self._lo is None or lo < self._lo:
            self._lo = lo
        if self._hi is None or hi > self._hi:
            self._hi = hi

    def _touch_removal(self, v):
        """删边记脏：v 可能可以往前挪，顺带看看它下游还有谁。"""
        self._dirty = True
        if self._cyclic:
            # 环还在的时候排不了，等标记清掉再说
            return
        pv = self._pos.get(v)
        if pv is None:
            self._rebuild = True
            return
        extent = self._descend_extent(v, pv)
        if extent is None:
            self._rebuild = True
        else:
            if self._lo is None or pv < self._lo:
                self._lo = pv
            if self._hi is None or extent > self._hi:
                self._hi = extent

    def _descend_extent(self, v, start):
        """v 和它下游最远的位置；查得太深返回 None，让调用方整图重排。"""
        seen = {v}
        stack = [v]
        farthest = start
        while stack:
            node = stack.pop()
            if len(seen) > _EXTENT_CAP:
                return None
            pos = self._pos.get(node)
            if pos is not None and pos > farthest:
                farthest = pos
            for succ in self._graph.successors(node):
                if succ not in seen:
                    seen.add(succ)
                    stack.append(succ)
        return farthest

    def _settle(self):
        """把积压的操作落到序上。"""
        if not self._dirty:
            return
        self._dirty = False
        if self._cyclic:
            # 环没清掉之前排不了，操作先搁着
            self._pending = []
            self._lo = None
            self._hi = None
            return
        if self._rebuild:
            self._rebuild = False
            self._recompute()
        else:
            self._repair()
        self._check_cycles()
        self._pending = []
        self._lo = None
        self._hi = None

    def _recompute(self):
        """整图重排，按加入序号出队。"""
        indeg = dict(self._indeg)
        ready = [(self._seq[node], node) for node in self._seq if indeg.get(node, 0) == 0]
        heapq.heapify(ready)
        order = []
        while ready:
            _, node = heapq.heappop(ready)
            order.append(node)
            for succ in self._graph.successors(node):
                indeg[succ] -= 1
                if indeg[succ] == 0:
                    heapq.heappush(ready, (self._seq[succ], succ))
        if len(order) != len(self._seq):
            # 账上还有节点出不了队，先按有环处理
            self._cyclic = True
            self._cycle_hint = self._pending[-1] if self._pending else None
        self._order = order
        self._pos = {node: index for index, node in enumerate(order)}

    def _repair(self):
        """只重排标脏的区间，区间外的次序不动。"""
        if self._lo is None:
            return
        lo, hi = self._lo, self._hi
        if lo < 0:
            lo = 0
        if hi >= len(self._order):
            hi = len(self._order) - 1
        if hi < lo:
            return
        window = self._order[lo:hi + 1]
        inside = set(window)
        counts = {}
        ready = set()
        for node in window:
            outside = 0
            for pred in self._graph.predecessors(node):
                if pred not in inside:
                    outside += 1
            count = self._indeg.get(node, 0) - outside
            counts[node] = count
            if count <= 0:
                ready.add(node)
        out = []
        placed = set()
        while ready:
            node = ready.pop()
            out.append(node)
            placed.add(node)
            for succ in self._graph.successors(node):
                if succ not in counts or succ in placed:
                    continue
                counts[succ] -= 1
                if counts[succ] <= 0:
                    ready.add(succ)
        leftover = [node for node in window if node not in placed]
        self._order = self._order[:lo] + out + leftover + self._order[hi + 1:]
        self._pos = {node: index for index, node in enumerate(self._order)}

    def _check_cycles(self):
        """环检测延迟到结算时做：单条新边查可达，一批新边整体查一遍。"""
        if self._cyclic or not self._pending:
            return
        if len(self._pending) == 1:
            u, v = self._pending[0]
            if self._reaches(v, u):
                self._cyclic = True
                self._cycle_hint = (u, v)
            return
        if not reference_is_acyclic(self._graph):
            self._cyclic = True
            self._cycle_hint = self._pending[-1]

    def _reaches(self, src, dst):
        """src 能不能顺边走到 dst，用来判新边有没有封出环。"""
        if src == dst:
            return True
        if not self._graph.successors(src):
            return False
        seen = {src}
        stack = [src]
        while stack:
            node = stack.pop()
            for succ in self._graph.successors(node):
                if succ == dst:
                    return True
                if succ not in seen:
                    seen.add(succ)
                    stack.append(succ)
        return False

    def order(self):
        """当前拓扑序；有环抛 CycleError。"""
        self._settle()
        if self._cyclic:
            raise CycleError("图中存在环，排不出拓扑序")
        return list(self._order)

    def is_acyclic(self):
        """当前图是不是无环图。"""
        self._settle()
        return not self._cyclic

    def in_degree(self, node):
        """节点当前入度，读的是引擎自己记的账。"""
        return self._indeg.get(node, 0)

    def rank(self, node):
        """节点在当前序里的位置，节点不存在返回 None。"""
        self._settle()
        return self._pos.get(node)

    def nodes(self):
        """节点加入顺序。"""
        return list(self._seq)

    def snapshot(self):
        """复制一份底层图，拿去对拍。"""
        graph = DiGraph()
        for node in self._seq:
            graph.add_node(node)
        for u in self._seq:
            for v in self._graph.successors(u):
                graph.add_edge(u, v)
        return graph
