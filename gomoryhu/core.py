"""gomoryhu 的改造前现状：只用逐对点最大流求全体点对最小割。

当前对外只有一条朴素路：给定一张无向图与它每个点对的容量口径，为了得到任意
两点之间的最小割，直接对这两个点各自跑一遍最大流，任意两个点都从头再来一遍，
代价随点对数量乘以一次最大流的时间上涨。实现只用整数容量与确定性的增广顺序，
结果可复现，但没有任何一次构造性的树形结构能把全体点对的最小割一次性压出来。
重建一棵戈莫里胡树、维护割侧代表、每次只跑点数减一次最大流这类做法见任务描述。
"""

__all__ = [
    "Erro",
    "GomoryHuError",
    "GraphError",
    "UnknownNodeError",
    "GomoryHu",
]


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class GraphError(Erro):
    """图参数、边表或容量口径不合法。"""


class UnknownNodeError(Erro):
    """查询引用了不在图中的结点编号。"""


# 保留一个更贴合题材的别名，便于调用方按语义捕捉异常。
GomoryHuError = GraphError


def _is_int(value):
    """是不是真正的整数，布尔值不算。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_capacity(value, name="capacity"):
    """容量必须是非负整数。"""
    if not _is_int(value):
        raise GraphError("%s must be an int" % name)
    if value < 0:
        raise GraphError("%s must not be negative" % name)
    return value


def _normalize(edges):
    """把无向边表整理成三元组列表，顺带校验并收集点集。

    每条边写成端点、端点、容量；容量必须是非负整数，自环直接拒绝。
    平行边合法，按多条独立边分别计入容量。
    """
    if edges is None:
        raise GraphError("edges must not be None")
    arcs = []
    nodes = []
    for edge in edges:
        try:
            length = len(edge)
        except TypeError:
            raise GraphError("each edge must be a sequence")
        if length != 3:
            raise GraphError("each edge is u, v, capacity")
        u = edge[0]
        v = edge[1]
        cap = _check_capacity(edge[2], "capacity")
        if u == v:
            raise GraphError("self loop is not allowed")
        try:
            hash(u)
            hash(v)
        except TypeError:
            raise GraphError("endpoints must be hashable")
        arcs.append((u, v, cap))
        if u not in nodes:
            nodes.append(u)
        if v not in nodes:
            nodes.append(v)
    return arcs, nodes


class GomoryHu:
    """绑定一张无向图，用逐对点最大流求两点间最小割。

    邻接表保存在实例上，模块级不持有任何可变状态；同一实例对固定输入重复
    查询结果一致。范式为整数容量与确定性的增广顺序，故结果完全可复现。
    """

    def __init__(self, edges):
        self._arcs, self._nodes = _normalize(edges)
        self._order = sorted(self._nodes)
        self._adj = {x: [] for x in self._order}
        for u, v, cap in self._arcs:
            self._adj[u].append((v, cap))
            self._adj[v].append((u, cap))
        for x in self._order:
            self._adj[x].sort()
        self._augment_count = 0

    # ------------------------------------------------------------------
    # 对外口径
    # ------------------------------------------------------------------
    def nodes(self):
        """返回图里出现的全部结点编号，按升序排列。"""
        return list(self._order)

    def node_count(self):
        """返回结点个数。"""
        return len(self._order)

    def has_edge(self, u, v):
        """两点之间是否存在至少一条边。"""
        self._check_node(u)
        self._check_node(v)
        for w, _cap in self._adj[u]:
            if w == v:
                return True
        return False

    def reset_augment_count(self):
        """把增广次数计数清零。"""
        self._augment_count = 0

    def augment_count(self):
        """自上次清零以来累计做了多少次增广。"""
        return self._augment_count

    def pair_cut(self, source, sink, edges=None):
        """求 source 与 sink 之间的最小割容量。

        朴素口径：每次都从头为这两个点单独跑一遍最大流。若给出 edges，
        就在这个边上集合上求解，否则用整张图的全部边。
        返回容量、可及的割侧点集（按升序）以及这次求解走的增广次数。
        """
        self._check_node(source)
        self._check_node(sink)
        if source == sink:
            raise GraphError("source and sink must differ")
        arcs, _nodes = _normalize(self._arcs if edges is None else edges)
        flow, reached, iterations = _max_flow(arcs, source, sink)
        self._augment_count += iterations
        return {
            "value": flow,
            "side": sorted(reached),
            "augmentations": iterations,
        }

    def all_pairs_cuts(self):
        """对所有无序点对逐一求最小割容量。

        任意两点都从头跑一遍最大流，代价随点对数量乘以一次最大流的时间上涨。
        返回编号较小者在前、按字典序排列的点对到容量的映射。
        """
        result = {}
        for i in range(len(self._order)):
            for j in range(i + 1, len(self._order)):
                u = self._order[i]
                v = self._order[j]
                result[(u, v)] = self.pair_cut(u, v)["value"]
        return result

    def pair_disjoint(self, x, y, w):
        """逐对点枚举口径下，判断 x 与 y 是否被点 w 隔开。

        点 w 与 x、y 都不同；把 w 与它关联的边一并删掉，再看 x 能否走到 y。
        返回真当且仅当删掉 w 之后 x 到 y 再无通路，即 x 到 y 的任一路径都
        必经 w。这一判断只看连通性，与边的容量无关。
        """
        for name in (x, y, w):
            self._check_node(name)
        if x == w or y == w:
            raise GraphError("the removed node must differ from both")
        if x == y:
            raise GraphError("source and sink must differ")
        seen = {x}
        stack = [x]
        while stack:
            u = stack.pop()
            for v, _cap in self._adj[u]:
                if v == w or v in seen:
                    continue
                seen.add(v)
                stack.append(v)
        return y not in seen

    def _check_node(self, u):
        if u not in self._adj:
            raise UnknownNodeError("unknown node: %r" % (u,))


def _max_flow(arcs, source, sink):
    """确定性最大流：每次在残量图上用广度优先找一条最短增广路。

    残量图的邻接表按结点编号与边编号共同排序，增广顺序固定，容量为整数，
    故同一次求解在重复运行下结果一致。返回流量、从源点可及的点集与增广次数。
    """
    cap = {}
    adj = {}
    origin = {}
    next_id = 0
    for u, v, c in arcs:
        if u == v:
            continue
        forward = next_id
        backward = next_id + 1
        next_id += 2
        cap[forward] = c
        cap[backward] = c
        origin[forward] = u
        origin[backward] = v
        adj.setdefault(u, []).append((v, forward, backward))
        adj.setdefault(v, []).append((u, backward, forward))
    for row in adj.values():
        row.sort()
    flow = 0
    iterations = 0
    while True:
        parent_edge = {source: None}
        queue = [source]
        head = 0
        found = False
        while head < len(queue):
            u = queue[head]
            head += 1
            for v, forward, _backward in adj.get(u, ()):
                if v not in parent_edge and cap[forward] > 0:
                    parent_edge[v] = forward
                    if v == sink:
                        found = True
                        break
                    queue.append(v)
            if found:
                break
        if not found:
            break
        path = []
        v = sink
        while v != source:
            eid = parent_edge[v]
            v = origin[eid]
            path.append(eid)
        path.reverse()
        bottleneck = None
        for eid in path:
            if bottleneck is None or cap[eid] < bottleneck:
                bottleneck = cap[eid]
        for eid in path:
            reverse = eid ^ 1
            cap[eid] -= bottleneck
            cap[reverse] += bottleneck
        flow += bottleneck
        iterations += 1
    reached = _reachable_in_residual(adj, cap, source)
    return flow, reached, iterations


def _reachable_in_residual(adj, cap, source):
    """残量图上从源点出发能到达的点集。"""
    seen = {source}
    stack = [source]
    while stack:
        u = stack.pop()
        for v, forward, _backward in adj.get(u, ()):
            if v not in seen and cap[forward] > 0:
                seen.add(v)
                stack.append(v)
    return seen
