"""mcfx.flow —— 改造前的朴素最小费用流实现。

这个模块只做两件事里的一件：要么只看流量不看费用（max_flow 的朴素逐条增广），
要么只看单条路径的费用（path_cost 的最短路）。它无法回答"既最大又最省"这种
把两个目标合起来的问题——那正是后续要补的能力。

朴素口径说明：
  - 每条边有容量 capacity 与单位费用 unit_cost，费用按"每单位流量"计。
  - 朴素增广只看容量，不看费用，所以得到的是最大流，但总费用没有保证。
  - path_cost 只取残量网络上从源到汇的单条最短路径，把它的费用当作粗略参考，
    既不保证是最大流下的最小值，也不覆盖多条路径叠加的情形。

纯标准库实现，不依赖任何第三方包。
"""

from collections import deque

#: 用于表示"无穷大"的容量下界，零容量边不参与任何计算。
INF = float("inf")


class McfError(Exception):
    """一切非法输入与非法操作的统一基类。"""


class CapacityError(McfError):
    """容量为负数、或流量超出容量约束时抛出。"""


class NodeError(McfError):
    """节点非法（未登记、或取值不适合作为端点）时抛出。"""


class InfeasibleError(McfError):
    """在 fail-fast 口径下，要求的流量无法送达时抛出。"""


class FlatMcf:
    """扁平邻接表表示的最小费用流工具（改造前朴素实现）。

    邻接表 adj 映射 节点名 -> 边列表，每条边是一个三元组 (u, v, capacity, unit_cost)。
    为了保持朴素，这里不做反向边的维护，增广过程只沿"原图方向"的边进行。
    """

    def __init__(self):
        self.adj = {}

    # ------------------------------------------------------------------
    # 构图
    # ------------------------------------------------------------------
    def add_node(self, name):
        """登记一个孤立节点。重复登记无副作用。"""
        if not isinstance(name, str) or name == "":
            raise NodeError("节点名必须是非空字符串")
        self.adj.setdefault(name, [])
        return name

    def add_edge(self, u, v, capacity, unit_cost):
        """加一条 u -> v 的有向边。

        capacity 必须是非负数；为负立即 fail fast。unit_cost 允许为负。
        平行边各自独立，不做合并。
        """
        if not isinstance(capacity, (int, float)) or isinstance(capacity, bool):
            raise CapacityError("容量必须是数值")
        if capacity < 0:
            raise CapacityError("容量不允许为负数")
        if not isinstance(unit_cost, (int, float)) or isinstance(unit_cost, bool):
            raise McfError("单位费用必须是数值")
        self.add_node(u)
        self.add_node(v)
        self.adj[u].append([u, v, capacity, unit_cost])
        return (u, v, capacity, unit_cost)

    def nodes(self):
        """返回所有节点名，按名字排序，保证调用间确定性。"""
        return sorted(self.adj.keys())

    def _require_node(self, name):
        if name not in self.adj:
            raise NodeError("节点未登记: %r" % (name,))

    # ------------------------------------------------------------------
    # 朴素最大流：逐条增广，只看容量不看费用
    # ------------------------------------------------------------------
    def max_flow(self, s, t):
        """朴素逐条增广求 s 到 t 的最大流，忽略费用。

        返回 (最大流量, 沿路费用合计)。沿路费用只是把增广走过的边的单位费用
        乘上实际推过的流量累加，没有任何最优性保证。

        增广在本次调用内部的剩余容量副本上进行，不改动图中已登记的边，
        因此同一张图可以反复调用，多次结果一致。
        """
        self._require_node(s)
        self._require_node(t)
        if s == t:
            return (0, 0)

        # 每次调用用一份独立的剩余容量副本，避免把图跑"空"。
        res = {}
        for adj in self.adj.values():
            for edge in adj:
                res[id(edge)] = edge[2]

        total = 0
        total_cost = 0
        while True:
            # 每次用一次 BFS 找一条仍有剩余容量的路径
            queue = deque([s])
            seen = {s: ("__none__", None)}  # node -> (prev_node, edge)
            while queue:
                cur = queue.popleft()
                if cur == t:
                    break
                for edge in self.adj[cur]:
                    _, v, cap, cost = edge
                    if res[id(edge)] > 0 and v not in seen:
                        seen[v] = (cur, edge)
                        queue.append(v)
            if t not in seen:
                break
            # 回溯求瓶颈
            bottleneck = INF
            cur = t
            while cur != s:
                prev, edge = seen[cur]
                bottleneck = min(bottleneck, res[id(edge)])
                cur = prev
            if bottleneck <= 0:
                break
            # 推流：只扣减本次调用的剩余容量副本，不建反向边
            cur = t
            path_cost_sum = 0
            while cur != s:
                prev, edge = seen[cur]
                res[id(edge)] -= bottleneck
                path_cost_sum += edge[3]
                cur = prev
            total += bottleneck
            total_cost += bottleneck * path_cost_sum
        return (total, total_cost)

    # ------------------------------------------------------------------
    # 单条最短路费用：只取一条路径当作粗略参考
    # ------------------------------------------------------------------
    def path_cost(self, s, t):
        """求残量网络上 s 到 t 的一条最短路，返回该路径的费用合计。

        没有路径返回 None。这里只用带权重的松弛（允许负数费用），不保证
        是"最大流前提下"的费用，也不覆盖多条路径叠加的情形。
        """
        self._require_node(s)
        self._require_node(t)
        if s == t:
            return 0

        dist = {name: INF for name in self.adj}
        dist[s] = 0
        # 简单松弛，规模小，够用；负权时靠有限轮数收敛
        for _ in range(len(self.adj)):
            updated = False
            for u in self.adj:
                if dist[u] == INF:
                    continue
                for edge in self.adj[u]:
                    _, v, cap, cost = edge
                    if cap > 0 and dist[u] + cost < dist[v]:
                        dist[v] = dist[u] + cost
                        updated = True
            if not updated:
                break
        if dist[t] == INF:
            return None
        return dist[t]

    # ------------------------------------------------------------------
    # 可行性判断：能否把 need 单位流量送达
    # ------------------------------------------------------------------
    def has_feasible(self, s, t, need):
        """判断能否把 need 单位流量从 s 送到 t。

        need 为负数 fail fast。need 为零时恒为可行（自身即满足）。
        """
        if not isinstance(need, (int, float)) or isinstance(need, bool):
            raise McfError("need 必须是数值")
        if need < 0:
            raise CapacityError("need 不允许为负数")
        if need == 0:
            return True
        self._require_node(s)
        self._require_node(t)
        if s == t:
            return False
        best, _ = self.max_flow(s, t)
        return best >= need
