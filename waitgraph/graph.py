"""等待图的拓扑结构：谁在等谁手里的资源。

边从等待者指向持有者。图只维护拓扑，不判断业务语义，也不做环检测。
遍历和整图枚举按碰到的节点数记到 visits 上，压测检测开销时拿它观测。
"""

import collections


class WaitGraph:
    """有向等待图。

    边以 (waiter, resource) 为键存 holder，一个等待者可以同时等多个
    持有者手里的不同资源。
    """

    def __init__(self):
        self._out = {}
        self._in = {}
        self.visits = 0

    # ---- 变更 ----

    def add_edge(self, waiter, holder, resource):
        """登记 waiter 等 holder 的 resource，返回被顶掉的旧 holder。"""
        slots = self._out.setdefault(waiter, {})
        prev = slots.get(resource)
        if prev is not None and prev != holder:
            self._take_in(prev, waiter, resource)
        slots[resource] = holder
        self._in.setdefault(holder, {}).setdefault(waiter, set()).add(resource)
        return prev

    def remove_edge(self, waiter, holder, resource):
        """按完整三元组精确删边，对不上就原样留着，返回是否删掉了。"""
        slots = self._out.get(waiter)
        if slots is None or slots.get(resource) != holder:
            return False
        del slots[resource]
        if not slots:
            del self._out[waiter]
        self._take_in(holder, waiter, resource)
        return True

    def remove_from(self, pid):
        """删掉 pid 作为等待者留下的边，返回删掉的条数。"""
        slots = self._out.pop(pid, None)
        if not slots:
            return 0
        for resource, holder in slots.items():
            self._take_in(holder, pid, resource)
        return len(slots)

    def remove_involving(self, pid):
        """删掉所有和 pid 沾边的等待边（它等的、别人等它的），返回条数。"""
        removed = 0
        slots = self._out.pop(pid, None)
        if slots:
            for resource, holder in slots.items():
                self._take_in(holder, pid, resource)
                removed += 1
        incoming = self._in.pop(pid, None)
        if incoming:
            for waiter, resources in incoming.items():
                waiter_slots = self._out.get(waiter)
                if not waiter_slots:
                    continue
                for resource in set(resources):
                    if waiter_slots.get(resource) == pid:
                        del waiter_slots[resource]
                        removed += 1
                if not waiter_slots:
                    del self._out[waiter]
        return removed

    def clear(self):
        """清空全图。"""
        self._out.clear()
        self._in.clear()

    def _take_in(self, holder, waiter, resource):
        by_waiter = self._in.get(holder)
        if not by_waiter:
            return
        resources = by_waiter.get(waiter)
        if not resources:
            return
        resources.discard(resource)
        if not resources:
            del by_waiter[waiter]
        if not by_waiter:
            del self._in[holder]

    # ---- 查询 ----

    def holders(self, waiter):
        """waiter 正在等的持有者，按资源登记顺序，可能重复。"""
        self.visits += 1
        return list(self._out.get(waiter, {}).values())

    def successors(self, waiter):
        """waiter 出边指向的节点，pid 升序去重。"""
        self.visits += 1
        return sorted(set(self._out.get(waiter, {}).values()))

    def predecessors(self, holder):
        """指向 holder 的等待者，pid 升序去重。"""
        self.visits += 1
        return sorted(self._in.get(holder, ()))

    def waiters_of(self, holder):
        """谁在等 holder 手里的资源。"""
        return list(self._in.get(holder, ()))

    def edge_of(self, waiter, resource):
        """waiter 对 resource 记的持有者，没有则 None。"""
        return self._out.get(waiter, {}).get(resource)

    def has_edge(self, waiter, holder):
        """waiter 有没有一条边指向 holder（任意资源），不计访问。"""
        return holder in self._out.get(waiter, {}).values()

    def target_count(self, waiter, holder):
        """waiter 指向 holder 的边有几条（按资源计），不计访问。"""
        return sum(1 for node in self._out.get(waiter, {}).values()
                   if node == holder)

    def waits(self):
        """全部等待边，元素是 (waiter, resource, holder)。"""
        return [(waiter, resource, holder)
                for waiter, slots in self._out.items()
                for resource, holder in slots.items()]

    def nodes(self):
        """图上出现过的节点，先等待者后持有者，各自保持登记顺序。

        枚举整图算一次批量读取，按节点数计入访问计数。
        """
        seen = self._collect_nodes()
        self.visits += len(seen)
        return list(seen)

    def node_count(self):
        """图上节点数，不计访问。"""
        return len(self._collect_nodes())

    def _collect_nodes(self):
        seen = {}
        for waiter, slots in self._out.items():
            seen.setdefault(waiter, None)
            for holder in slots.values():
                seen.setdefault(holder, None)
        for holder in self._in:
            seen.setdefault(holder, None)
        return seen

    def walk(self, start):
        """从 start 沿等待边广度优先走一遍，返回访问到的节点集合。"""
        seen = {start}
        queue = collections.deque([start])
        while queue:
            node = queue.popleft()
            for nxt in self.holders(node):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def reachable(self, src, dst):
        """src 能不能沿等待边走到 dst。"""
        return src == dst or dst in self.walk(src)
