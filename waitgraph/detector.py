"""等待图上的死锁检测。

registry 在每次等待关系变动时把事件喂给检测器，检测器维护一份等待图，
回答有没有环、环上是谁。waitgraph.oracle 里的全量实现是这份行为的契约
基准，两边对拍。

判定只认当前图：结论随每次变动即时刷新，删边立刻解除报警，不残留任何
历史边或历史结论。实现上按强连通分量（SCC）做增量维护，单次变动只从
变动相关的节点做局部遍历，不扫整图；环上成员即真正成环的 SCC 内节点，
截取和排序规则与 waitgraph.oracle.FullScan 完全一致。
"""

import collections

from .graph import WaitGraph


class DeadlockDetector:
    """检测器：收变动事件，答死锁判定与环成员。"""

    def __init__(self):
        self.graph = WaitGraph()
        self._comp = {}
        self._members = {}
        self._next_label = 0
        self._cyclic = set()
        self._deadlocked = False
        self._cycle = []

    # ---- 事件入口，由 registry 调用 ----

    def note_wait(self, waiter, holder, resource):
        """新等待：waiter 开始等 holder 手里的 resource。"""
        prev = self.graph.edge_of(waiter, resource)
        if prev == holder:
            return
        # 旧图上对跑：holder 前向可达 waiter（等价于 waiter 反向可达
        # holder）时新边才闭环；删边不可能破坏这个判定。
        forward = self._walk(holder, self.graph.successors)
        backward = self._walk(waiter, self.graph.predecessors)
        closes = waiter in forward and holder in backward
        removing_old = (prev is not None and self.graph.target_count(waiter, prev) == 1)
        self.graph.add_edge(waiter, holder, resource)
        self._ensure_node(waiter)
        self._ensure_node(holder)
        if removing_old:
            self._split_scc(waiter, prev)
        if closes:
            self._merge(waiter, holder)
        self._refresh()

    def note_wake(self, waiter, resource, donor):
        """等待结束：donor 把手里的 resource 放给了 waiter。"""
        removed = self.graph.remove_edge(waiter, donor, resource)
        if removed:
            self._split_scc(waiter, donor)
            self._refresh()

    def note_drop(self, pid):
        """进程失联：它等的、别人等它的边全部作废。"""
        label = self._comp.get(pid)
        self.graph.remove_involving(pid)
        # 被删的跨分量边不影响 SCC；所有可能裂开的分量内边都连着 pid，
        # 所以只需重算 pid 原来所在的那一个分量。
        if label is not None:
            self._split_scc(pid)
        if not self.graph.holders(pid) and not self.graph.waiters_of(pid):
            stale = self._comp.pop(pid, None)
            if stale is not None:
                self._members.pop(stale, None)
                self._cyclic.discard(stale)
        self._refresh()

    def rebuild(self, edges):
        """整体重建（启动加载快照）：edges 是 (waiter, resource, holder)。"""
        self.graph.clear()
        for waiter, resource, holder in edges:
            self.graph.add_edge(waiter, holder, resource)
        self._rebuild_components()
        self._refresh()

    # ---- 查询 ----

    def deadlocked(self):
        """现在有没有死锁。"""
        return self._deadlocked

    def cycle_members(self):
        """环上成员列表，没有环时为空。"""
        return list(self._cycle)

    def stats(self):
        """检测过程的访问计数：遍历和整图枚举碰到的节点数。"""
        return {"visits": self.graph.visits, "nodes": self.graph.node_count()}

    def reset_stats(self):
        """访问计数归零。"""
        self.graph.visits = 0

    # ---- 增量 SCC 维护 ----

    def _merge(self, src, dst):
        """新边 src->dst 闭环：把受影响的 SCC 合成一个，成员取新旧可达交集。"""
        forward = self._walk(src, self.graph.successors)
        backward = self._walk(dst, self.graph.predecessors)
        region = forward & backward
        labels = {self._comp[node] for node in region}
        label = self._new_label()
        for old in labels:
            self._cyclic.discard(old)
            self._members.pop(old, None)
        for node in region:
            self._comp[node] = label
        self._members[label] = region
        self._cyclic.add(label)

    def _split_scc(self, src, dst=None):
        """删边后在受影响分量内部重算 SCC；两端不同分量则什么都不会变。"""
        if dst is not None and self._comp.get(src) != self._comp.get(dst):
            return
        label = self._comp.get(src)
        if label is None:
            return
        members = self._members.pop(label)
        self._cyclic.discard(label)
        if len(members) == 1:
            only = next(iter(members))
            self._members[label] = members
            if self.graph.has_edge(only, only):
                self._cyclic.add(label)
            return
        components = self._kosaraju(members)
        for cid, component in enumerate(components):
            new_label = self._new_label()
            component_set = set(component)
            cyclic = (len(component) > 1
                      or any(self.graph.has_edge(n, n) for n in component))
            for member in component:
                self._comp[member] = new_label
            self._members[new_label] = component_set
            if cyclic:
                self._cyclic.add(new_label)

    def _rebuild_components(self):
        """全图 Kosaraju，只在启动快照恢复时走一次。"""
        self._comp = {}
        self._members = {}
        self._next_label = 0
        self._cyclic = set()
        components = self._kosaraju(set(self.graph.nodes()))
        for cid, component in enumerate(components):
            label = self._new_label()
            cyclic = (len(component) > 1
                      or any(self.graph.has_edge(n, n) for n in component))
            for node in component:
                self._comp[node] = label
            self._members[label] = set(component)
            if cyclic:
                self._cyclic.add(label)

    def _new_label(self):
        label = self._next_label
        self._next_label += 1
        return label

    def _ensure_node(self, node):
        """首次出现的节点先登记成独立的非环分量。"""
        if node not in self._comp:
            label = self._new_label()
            self._comp[node] = label
            self._members[label] = {node}

    def _kosaraju(self, nodes):
        """限定节点集合内的 Kosaraju，返回各 SCC 的成员列表。"""
        order = []
        seen = set()
        for root in nodes:
            if root in seen:
                continue
            seen.add(root)
            stack = [(root, iter(self.graph.successors(root)))]
            while stack:
                node, iterator = stack[-1]
                nxt = next(iterator, None)
                if nxt is None:
                    order.append(node)
                    stack.pop()
                    continue
                if nxt in nodes and nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, iter(self.graph.successors(nxt))))
        result = []
        assigned = set()
        for root in reversed(order):
            if root in assigned:
                continue
            assigned.add(root)
            component = []
            stack = [root]
            while stack:
                node = stack.pop()
                component.append(node)
                for nxt in self.graph.predecessors(node):
                    if nxt in nodes and nxt not in assigned:
                        assigned.add(nxt)
                        stack.append(nxt)
            result.append(component)
        return result

    def _walk(self, start, neighbors):
        """从 start 按去重邻接做一次广度遍历。"""
        seen = {start}
        queue = collections.deque([start])
        while queue:
            node = queue.popleft()
            for nxt in neighbors(node):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    # ---- 结论：规则与 oracle.FullScan 逐字一致 ----

    def _refresh(self):
        """只看当前图，重算死锁判定与环成员。"""
        if not self._cyclic:
            self._deadlocked = False
            self._cycle = []
            return
        roots = set()
        for label in self._cyclic:
            roots.update(self._members[label])
        reachable = set(roots)
        queue = collections.deque(roots)
        while queue:
            node = queue.popleft()
            for nxt in self.graph.predecessors(node):
                if nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)
        root = min(reachable)
        cycle = self._oracle_cycle(root)
        self._deadlocked = cycle is not None
        self._cycle = cycle or []

    def _oracle_cycle(self, root):
        """复刻 FullScan：升序根、升序后继，回边落点截断并旋到最小 pid。"""
        path = [root]
        on_path = {root}
        frames = [[root, iter(self.graph.successors(root))]]
        while frames:
            frame = frames[-1]
            nxt = next(frame[1], None)
            if nxt is None:
                frames.pop()
                path.pop()
                on_path.discard(frame[0])
                continue
            if nxt in on_path:
                cycle = path[path.index(nxt):]
                start = cycle.index(min(cycle))
                return cycle[start:] + cycle[:start]
            path.append(nxt)
            on_path.add(nxt)
            frames.append([nxt, iter(self.graph.successors(nxt))])
        return None
