"""有向图的朴素拓扑序计数：一条路走到底，全靠全排列枚举。

做法是把全部顶点排成序列，再逐个校验每条边是否都是从前指向后。是否存在
拓扑序、拓扑序有多少个、字典序最小的拓扑序是哪一个，都靠把全排列过一遍。
顶点一多，排列数按阶乘增长，很慢，但结果正确。
"""

import itertools


class TopoCountError(Exception):
    """本模块所有异常的基类。"""


class InvalidGraphError(TopoCountError):
    """图的规模或边的定义不合法。"""


class NodeNotFoundError(TopoCountError):
    """查询里出现了不在本图中的点编号。"""


def brute_permutations(n, edges):
    """枚举 0 到 n-1 的全部排列，逐个校验每条边的方向。

    对每个排列先记一次排列访问，再逐条边检查，每检查一条记一次边检查；
    返回 (访问的排列数, 边检查次数)。
    """
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise InvalidGraphError("点数必须是非负整数")
    edges = _clean_edges(n, edges)
    nodes = list(range(n))
    perm_visits = 0
    edge_checks = 0
    for perm in itertools.permutations(nodes):
        perm_visits += 1
        pos = {}
        for i, v in enumerate(perm):
            pos[v] = i
        for u, v in edges:
            edge_checks += 1
            if pos[u] >= pos[v]:
                break
    return [perm_visits, edge_checks]


def _clean_edges(n, edges):
    """校验并归一化边表，返回 (u, v) 的列表。"""
    if not isinstance(edges, (list, tuple)):
        raise InvalidGraphError("边集必须是列表或元组")
    out = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2:
            raise InvalidGraphError("每条边必须是两个端点的二元组")
        u, v = e[0], e[1]
        if not isinstance(u, int) or isinstance(u, bool):
            raise InvalidGraphError("端点编号必须是整数")
        if not isinstance(v, int) or isinstance(v, bool):
            raise InvalidGraphError("端点编号必须是整数")
        if not (0 <= u < n) or not (0 <= v < n):
            raise InvalidGraphError("端点 %r 或 %r 越界" % (u, v))
        out.append((u, v))
    return out


class DAGCounter(object):
    """一张有向图，用全排列枚举回答与拓扑序有关的全部问题。

    点编号取 0 到 n-1，边以 (u, v) 的形式按输入先后给出，表示由 u 指向 v。
    允许自环与平行边。构造时校验结构，之后只读。
    """

    def __init__(self, n, edges):
        if not isinstance(n, int) or isinstance(n, bool):
            raise InvalidGraphError("点数必须是整数")
        if n < 0:
            raise InvalidGraphError("点数不能为负")
        self._n = n
        self._edges = _clean_edges(n, edges)
        self.reset_counters()

    # ------------------------------------------------------------------
    # 计数
    # ------------------------------------------------------------------
    def reset_counters(self):
        self._counters = {"perm_visits": 0, "edge_checks": 0}

    def counters(self):
        """上一次枚举留下的计数副本。"""
        return dict(self._counters)

    def _bump(self, perm_visits, edge_checks):
        self._counters["perm_visits"] += perm_visits
        self._counters["edge_checks"] += edge_checks

    # ------------------------------------------------------------------
    # 基本访问
    # ------------------------------------------------------------------
    def node_count(self):
        return self._n

    def edge_count(self):
        return len(self._edges)

    def nodes(self):
        """全部点编号的升序列表。"""
        return list(range(self._n))

    def edges(self):
        """全部边，按输入先后给出 (u, v) 的列表。"""
        return list(self._edges)

    def _require_node(self, node):
        if not isinstance(node, int) or isinstance(node, bool):
            raise NodeNotFoundError("点 %r 不在图中" % (node,))
        if not 0 <= node < self._n:
            raise NodeNotFoundError("点 %r 不在图中" % (node,))

    def successor_map(self):
        """出边表：点编号到直接后继列表。"""
        out = {}
        for v in self.nodes():
            out[v] = []
        for u, v in self._edges:
            out[u].append(v)
        return out

    def predecessor_map(self):
        """入边表：点编号到直接前驱列表。"""
        out = {}
        for v in self.nodes():
            out[v] = []
        for u, v in self._edges:
            out[v].append(u)
        return out

    def in_degrees(self):
        """每个点的入度，按点编号升序给出。"""
        deg = [0] * self._n
        for u, v in self._edges:
            deg[v] += 1
        return deg

    # ------------------------------------------------------------------
    # 全排列枚举：所有拓扑相关问题都走这一条路
    # ------------------------------------------------------------------
    def topological_orders(self):
        """全部拓扑序，按字典序升序给出；有环时返回空列表。"""
        orders = []
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if self._is_valid(perm):
                orders.append(list(perm))
        return orders

    def _is_valid(self, perm):
        pos = {}
        for i, v in enumerate(perm):
            pos[v] = i
        for u, v in self._edges:
            self._counters["edge_checks"] += 1
            if pos[u] >= pos[v]:
                return False
        return True

    def has_topological_order(self):
        """是否存在拓扑序，也就是图是否有环的否命题。"""
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if self._is_valid(perm):
                return True
        return False

    def count_topological_orders(self):
        """拓扑序的个数；有环时为零。"""
        total = 0
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if self._is_valid(perm):
                total += 1
        return total

    def min_topological_order(self):
        """字典序最小的拓扑序；有环时返回 None。"""
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if self._is_valid(perm):
                return list(perm)
        return None

    def max_weight_order(self, weight):
        """在所有拓扑序里取顶点权和最大者，返回 (最大权和, 一个达到它的拓扑序)。

        weight 可以是按点编号给出的列表，也可以是点编号到权值的映射。
        按权值相加的口径比较，权值不参与顶点排序；有环时返回 None。
        """
        w = self._weights(weight)
        best = None
        best_order = None
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if not self._is_valid(perm):
                continue
            total = 0
            for v in perm:
                total += w[v]
            if best is None or total > best:
                best = total
                best_order = list(perm)
        if best is None:
            return None
        return (best, best_order)

    def position_ranges(self):
        """每个点在各拓扑序里出现位置的最小值与最大值。

        返回按点编号升序的 (最小值, 最大值) 列表；有环时返回 None。
        """
        low = [None] * self._n
        high = [None] * self._n
        seen_any = False
        for perm in itertools.permutations(self.nodes()):
            self._counters["perm_visits"] += 1
            if not self._is_valid(perm):
                continue
            seen_any = True
            for i, v in enumerate(perm):
                if low[v] is None or i < low[v]:
                    low[v] = i
                if high[v] is None or i > high[v]:
                    high[v] = i
        if not seen_any:
            return None
        out = []
        for v in self.nodes():
            if low[v] is None:
                low[v] = 0
                high[v] = 0
            out.append((low[v], high[v]))
        return out

    def _weights(self, weight):
        if isinstance(weight, dict):
            out = []
            for v in self.nodes():
                if v not in weight:
                    raise InvalidGraphError("点 %r 缺少权值" % (v,))
                out.append(self._one_weight(weight[v]))
            return out
        if isinstance(weight, (list, tuple)):
            if len(weight) != self._n:
                raise InvalidGraphError("权值表的长度必须等于点数")
            out = []
            for x in weight:
                out.append(self._one_weight(x))
            return out
        raise InvalidGraphError("权值必须是列表或按点编号的映射")

    def _one_weight(self, x):
        if not isinstance(x, int) or isinstance(x, bool):
            raise InvalidGraphError("权值必须是整数")
        return x
