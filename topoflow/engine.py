"""增量拓扑引擎。

IncrementalTopo 在 DiGraph 上维护一份可以复用的拓扑序，结果口径与
reference.py 完全一致：同层节点按节点加入序号（seq）出队，所以每张图、
每个节点加入顺序只对应唯一的一份序，跟增删的历史路径无关。

增删边先记进净变化账 _delta（同一条边重复增删会互相抵消，不会重复
记账；入度直接读底层 DiGraph，不会被减成负数），查询时才结算：

- 加边若在当前序里就是正向（u 在 v 前面），规范序不变，不动；
- 删边只可能让 v 提前，用线段树在 O(log n) 内找到 v 最早能抢到的
  位置，只对这个极小窗口重放一段 Kahn 过程，窗口外的节点位置不动；
- 加边若在当前序里反向（u 在 v 后面），重放 [pos(v), pos(u)] 窗口；
- 一批变化把上面的窗口取并集。窗口重放期间按 seq 出队，并允许窗口
  向两侧扩张把插队的窗口外节点和被外部依赖挡住的节点纳入；窗口里
  解不开的残圈才判环，扩张次数超限时退回整图重算兜底。

这样一条不改变规范序的删边（例如十万长链中间删一条）只做 O(log n)
的局部工作，不碰图的其余部分。
"""

import heapq

from topoflow.graph import DiGraph
from topoflow.reference import CycleError


# 窗口重放最多扩张重试多少次，超过就整图重算兜底（结果始终正确）
_MAX_RESTARTS = 64


class _SeqTree:
    """order 上按 seq 取值的线段树。

    支持单点改值，以及 first_greater(lo, hi, value)：区间 [lo, hi] 内
    第一个 seq > value 的下标；没有则返回 None。叶子不够时翻倍重建。
    """

    def __init__(self):
        self._base = 1
        self._data = [-1] * 2

    def rebuild(self, order, seq):
        n = len(order)
        base = 1
        while base < n:
            base *= 2
        data = [-1] * (2 * base)
        for i, node in enumerate(order):
            data[base + i] = seq[node]
        for i in range(base - 1, 0, -1):
            left = data[2 * i]
            right = data[2 * i + 1]
            data[i] = left if left >= right else right
        self._base = base
        self._data = data

    def set_value(self, index, value, length):
        if length > self._base:
            self.rebuild_pad(length)
        pos = self._base + index
        self._data[pos] = value
        pos //= 2
        while pos:
            left = self._data[2 * pos]
            right = self._data[2 * pos + 1]
            self._data[pos] = left if left >= right else right
            pos //= 2

    def rebuild_pad(self, length):
        base = self._base
        while base < length:
            base *= 2
        data = [-1] * (2 * base)
        # 逐叶复制旧值，简单可靠；只在容量翻倍时发生。
        old_base = self._base
        old = self._data
        for i in range(min(length, old_base)):
            data[base + i] = old[old_base + i]
        for i in range(base - 1, 0, -1):
            left = data[2 * i]
            right = data[2 * i + 1]
            data[i] = left if left >= right else right
        self._base = base
        self._data = data

    def first_greater(self, lo, hi, value):
        """[lo, hi]（含两端）里第一个 seq > value 的下标，找不到返回 None。"""
        if lo > hi or lo < 0:
            return None
        if hi >= self._base:
            hi = self._base - 1
        stack = [(1, 0, self._base - 1)]
        while stack:
            node, nl, nr = stack.pop()
            if nr < lo or nl > hi or self._data[node] <= value:
                continue
            if nl == nr:
                return nl
            mid = (nl + nr) // 2
            stack.append((2 * node + 1, mid + 1, nr))
            stack.append((2 * node, nl, mid))
        return None


class IncrementalTopo:
    """增量拓扑排序。

    增删入口：add_node / add_edge / remove_edge / add_edges / remove_edges，
    查询入口：order / is_acyclic / in_degree / rank / nodes / snapshot。
    remove_edge 删一条不存在的边返回 False；order 有环抛 CycleError。
    """

    def __init__(self):
        self._graph = DiGraph()
        self._seq = {}           # node -> 加入序号
        self._order = []         # 最近一次排出的序（有环时只是内部缓存）
        self._pos = {}           # node -> 在序里的位置
        self._cyclic = False     # 当前图是否有环
        self._dirty = False
        # 自上次结算以来的净变化：(u, v) -> +1 净新增 / -1 净删除。
        # 重复的加边/删边在这里互相抵消，账本永远不会被记歪。
        self._delta = {}
        self._tree = _SeqTree()
        # 本周期内被触碰过的边，在周期开始时是否已存在；只懒登记
        # 触碰过的键，避免 O(E) 快照。
        self._origin = {}

    def add_node(self, node):
        """登记一个节点，已存在返回 False。"""
        if node in self._seq:
            return False
        self._graph.add_node(node)
        self._seq[node] = len(self._seq)
        index = len(self._order)
        self._order.append(node)
        self._pos[node] = index
        self._tree.set_value(index, self._seq[node], index + 1)
        return True

    def add_edge(self, u, v):
        """加一条边，返回是否新加了边。"""
        self._ensure(u)
        self._ensure(v)
        key = (u, v)
        if self._graph.has_edge(u, v):
            return False
        # 真正改变图的操作才记账；此刻边不在图里，若本周期还没碰过
        # 它，说明它在周期开始时也不在（出身为 False）。
        self._open_period()
        if key not in self._origin:
            self._origin[key] = False
        self._graph.add_edge(u, v)
        self._delta[key] = self._delta.get(key, 0) + 1
        return True

    def add_edges(self, pairs):
        """批量加边，导入工具的主入口。"""
        for u, v in pairs:
            self._ensure(u)
            self._ensure(v)
            key = (u, v)
            if self._graph.has_edge(u, v):
                continue
            self._open_period()
            if key not in self._origin:
                self._origin[key] = False
            self._graph.add_edge(u, v)
            self._delta[key] = self._delta.get(key, 0) + 1

    def remove_edge(self, u, v):
        """删一条边，返回是否真的删掉了。"""
        if not self._graph.has_edge(u, v):
            return False
        key = (u, v)
        self._open_period()
        if key not in self._origin:
            self._origin[key] = True
        self._graph.remove_edge(u, v)
        self._delta[key] = self._delta.get(key, 0) - 1
        return True

    def remove_edges(self, pairs):
        """批量删边，回放删边日志走这个入口。"""
        for u, v in pairs:
            if not self._graph.has_edge(u, v):
                continue
            key = (u, v)
            self._open_period()
            if key not in self._origin:
                self._origin[key] = True
            self._graph.remove_edge(u, v)
            self._delta[key] = self._delta.get(key, 0) - 1

    # ---- 记账与结算 ----------------------------------------------------

    def _open_period(self):
        if not self._dirty:
            self._dirty = True

    def _ensure(self, node):
        if node not in self._seq:
            self.add_node(node)

    def _settle(self):
        """把积压的操作落到序上。"""
        if not self._dirty:
            return
        delta = self._net_changes()
        if self._cyclic:
            # 环状态下旧序只是缓存：删边可能破环也可能没破，新增边
            # 同样可能改变破环后的答案，统一整图重算拿权威结果。
            self._recompute()
            self._finish_period()
            return
        for lo, hi in self._initial_windows(delta):
            if not self._repair(lo, hi):
                # 窗口重放失败要么是环、要么是扩张超限：环时整图
                # Kahn 自然只排出无环节点并落 cyclic，超限则拿到
                # 权威全序，两种情况都靠整图重算收口。
                self._recompute()
                break
        self._finish_period()

    def _finish_period(self):
        """结算成功后提交账本。"""
        self._dirty = False
        self._delta = {}
        self._origin = {}

    def _net_changes(self):
        """把触碰计数折算成相对周期开始时的净变化。

        返回 (u, v) -> +1/-1：出身存在且计数为负是净删除，出身不存在
        且计数为正是净新增，其余（加了又删、删了又加）净变化为零。
        """
        changes = {}
        for key, count in self._delta.items():
            existed = self._origin.get(key, False)
            if existed:
                if count < 0:
                    changes[key] = -1
            else:
                if count > 0:
                    changes[key] = 1
        return changes

    def _initial_windows(self, delta):
        """根据净变化算出一组互不重叠的初始重放窗口。

        一条变化对应一个区间：反向新增边是 [pos(v), pos(u)]，删边是
        [v 最早能抢到的位置, pos(v)]（抢不到就是序不变，跳过）。
        互相重叠/相邻的区间合并，相隔的区间各自独立重放——长链上
        散落的几百条删边因此是几百个 O(log n) 小窗口，而不是一整条
        覆盖全图的大窗口。
        """
        spans = []
        for (u, v), sign in delta.items():
            pu = self._pos[u]
            pv = self._pos[v]
            if sign == 1:
                if pu >= pv:
                    # 反向新增边（含自环）：v 必须挪到 u 后面。
                    # 自环在单点窗口里必然解不开，照样判环。
                    spans.append((pv, pu))
                # pu < pv 的正向新增边不改变规范序，不贡献窗口
            else:
                # 删边只可能让 v 提前。v 最早能抢到的位置：从“最后
                # 一个仍在前驱落位之后”起，旧序里第一个 seq 比 v 大
                # 的位置；抢不到就说明序不变，这条删边不用重排。
                start = 0
                for pred in self._graph.predecessors(v):
                    pp = self._pos[pred]
                    if pp + 1 > start:
                        start = pp + 1
                win_lo = self._tree.first_greater(start, pv - 1, self._seq[v])
                if win_lo is not None:
                    spans.append((win_lo, pv))
        if not spans:
            return []
        spans.sort()
        windows = []
        cur_lo, cur_hi = spans[0]
        for lo, hi in spans[1:]:
            if lo <= cur_hi + 1:
                if hi > cur_hi:
                    cur_hi = hi
            else:
                windows.append((cur_lo, cur_hi))
                cur_lo, cur_hi = lo, hi
        windows.append((cur_lo, cur_hi))
        return windows

    def _recompute(self):
        """整图重排（Kahn，按 seq 出队），顺便落环标记。"""
        indeg = {node: self._graph.in_degree(node) for node in self._seq}
        ready = [(self._seq[node], node)
                 for node in self._seq if indeg[node] == 0]
        heapq.heapify(ready)
        order = []
        while ready:
            _, node = heapq.heappop(ready)
            order.append(node)
            for succ in self._graph.successors(node):
                indeg[succ] -= 1
                if indeg[succ] == 0:
                    heapq.heappush(ready, (self._seq[succ], succ))
        self._order = order
        self._pos = {node: index for index, node in enumerate(order)}
        self._tree.rebuild(order, self._seq)
        self._cyclic = len(order) != len(self._seq)

    def _repair(self, lo, hi):
        """窗口化重放 Kahn，窗口外节点位置不动。

        返回 True 表示窗口排出了合法且规范的结果并已就地落账；
        False 表示发现环或扩张超限，调用方应整图重算。
        """
        n = len(self._order)
        for _ in range(_MAX_RESTARTS):
            if lo < 0:
                lo = 0
            if hi >= n:
                hi = n - 1
            if lo > hi:
                return False
            window = self._order[lo:hi + 1]
            inside = set(window)

            # 窗口内剩余入度：只数落在窗口里的前驱；窗口右侧前驱挡着
            # 的窗口节点初始不可出队。
            counts = {}
            ready = []
            for node in window:
                count = 0
                for pred in self._graph.predecessors(node):
                    if pred in inside:
                        count += 1
                    elif self._pos[pred] > hi:
                        count += 1  # 外部前驱，窗口结束前不会落位
                counts[node] = count
                if count == 0:
                    heapq.heappush(ready, (self._seq[node], node))

            # 窗口外可能“插队”的候选 siren：有窗口内前驱，且其余前驱
            # 都已经在新前缀（位置 < lo）落位，只差窗口里这几个前驱。
            sirens = {}
            for node in window:
                for succ in self._graph.successors(node):
                    if succ in inside or succ in sirens:
                        continue
                    wait = 0
                    blocked = False
                    for pred in self._graph.predecessors(succ):
                        if pred in inside:
                            wait += 1
                        elif self._pos[pred] >= lo:
                            blocked = True
                            break
                    if not blocked:
                        sirens[succ] = wait
            siren_heap = [(self._seq[node], node)
                          for node, wait in sirens.items() if wait == 0]
            heapq.heapify(siren_heap)

            out = []
            placed = set()
            intrude = None
            while len(placed) < len(window):
                # 规范序要求此刻 seq 最小的 zero 节点先出：窗口外若有
                # 更小的 zero 节点要插队，扩窗把它纳入后重放。
                if ready:
                    if siren_heap and siren_heap[0][0] < ready[0][0]:
                        _, intruder = heapq.heappop(siren_heap)
                        if sirens.get(intruder, 1) != 0:
                            continue
                        intrude = self._pos[intruder]
                        break
                    _, node = heapq.heappop(ready)
                    out.append(node)
                    placed.add(node)
                elif siren_heap:
                    _, intruder = heapq.heappop(siren_heap)
                    if sirens.get(intruder, 1) != 0:
                        continue
                    # 窗口内已无节点可出，窗口外却有 zero 节点：正常图
                    # 里这只会是插队（settled 旧序保证它旧账上不可能这么
                    # 早 zero），扩窗纳入；扩进来仍解不开就整图重算。
                    intrude = self._pos[intruder]
                    break
                else:
                    # 窗口里有节点始终出不了队，又没有可扩的外部节点：
                    # 残圈就在窗口内。
                    return False
                for succ in self._graph.successors(node):
                    if succ in inside:
                        if succ not in placed:
                            counts[succ] -= 1
                            if counts[succ] == 0:
                                heapq.heappush(ready, (self._seq[succ], succ))
                    else:
                        wait = sirens.get(succ)
                        if wait is None:
                            # 未登记的窗口后继：说明它被窗口右侧前驱挡
                            # 着（旧序正向边下本不该发生，防御性兜底）。
                            return False
                        wait -= 1
                        sirens[succ] = wait
                        if wait == 0:
                            heapq.heappush(siren_heap,
                                           (self._seq[succ], succ))

            if intrude is not None:
                # siren 都是窗口右侧节点（旧序正向边 + 新边窗口并集保证）。
                if intrude <= hi:
                    return False
                hi = intrude
                continue

            if out != window:
                self._order[lo:hi + 1] = out
                for offset, node in enumerate(out):
                    index = lo + offset
                    self._pos[node] = index
                    self._tree.set_value(index, self._seq[node], n)
            return True
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
        """节点当前入度，直接读底层图的账，重复增删不会记歪。"""
        return self._graph.in_degree(node)

    def rank(self, node):
        """节点在当前序里的位置；有环或节点不存在返回 None。"""
        self._settle()
        if self._cyclic:
            return None
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
