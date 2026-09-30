"""mincut 的网络割工具（改造前的现状）。

现在只有一条朴素路：求源汇最小割时，枚举全部边子集，逐个丢掉后看源点还能不能
走到汇点，在所有能割开的子集里挑容量最小、边数最少的那一组；判断某组边是不是
割，也是丢掉这组边再走一遍连通性；判断给定容量下有没有更小的割，同样靠枚举。
结果都对，但边一多，枚举的子集数就随边数指数上涨。最大流分层增广、收缩合并这
类做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class GraphError(Erro):
    """图参数或边表非法。"""


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


def _normalize(edges, directed):
    """把边表整理成定长四元组，顺带校验并收集点集。

    每条边写成起点、终点、容量、边编号；只给三元组时边编号取它在表里的位置。
    自环直接拒绝，容量必须非负，边编号不得重复。
    """
    if edges is None:
        raise GraphError("edges must not be None")
    arcs = []
    nodes = set()
    seen = set()
    for index, edge in enumerate(edges):
        try:
            length = len(edge)
        except TypeError:
            raise GraphError("each edge must be a sequence")
        if length < 3 or length > 4:
            raise GraphError("each edge is start, end, capacity, id")
        u = edge[0]
        v = edge[1]
        cap = _check_capacity(edge[2], "capacity")
        if length == 4:
            eid = edge[3]
            if not _is_int(eid):
                raise GraphError("edge id must be an int")
        else:
            eid = index
        if eid in seen:
            raise GraphError("edge id must be unique")
        seen.add(eid)
        if u == v:
            raise GraphError("self loop is not allowed")
        try:
            hash(u)
            hash(v)
        except TypeError:
            raise GraphError("start and end must be hashable")
        arcs.append((u, v, cap, eid))
        nodes.add(u)
        nodes.add(v)
    return arcs, nodes


def _check_directed(directed):
    """口径只能是真（有向）或假（无向）。"""
    if not isinstance(directed, bool):
        raise GraphError("directed must be a bool")
    return directed


def _check_nodes(source, sink):
    """源汇相等是非法请求。"""
    if source == sink:
        raise GraphError("source and sink must differ")


def reachable(arcs, source, blocked, directed):
    """丢掉 blocked 里的边后，从源点能走到的点集，深度优先的朴素遍历。"""
    adjacency = {}
    for u, v, _cap, eid in arcs:
        if eid in blocked:
            continue
        adjacency.setdefault(u, []).append(v)
        if not directed:
            adjacency.setdefault(v, []).append(u)
    seen = {source}
    stack = [source]
    while stack:
        node = stack.pop()
        for nxt in adjacency.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _crossing(arc, side, directed):
    """这条边是不是从源侧跨到汇侧。无向边恰好一端在源侧就算跨越。"""
    u, v, _cap, _eid = arc
    if directed:
        return u in side and v not in side
    in_u = u in side
    in_v = v in side
    return in_u != in_v


def _boundary(arcs, side, directed):
    """源侧集合与汇侧集合之间的那组边，返回按边编号升序的编号列表。"""
    eids = [arc[3] for arc in arcs if _crossing(arc, side, directed)]
    eids.sort()
    return eids


def _capacity_of(arcs, side, directed):
    """源侧集合对应的割容量。"""
    total = 0
    for arc in arcs:
        if _crossing(arc, side, directed):
            total += arc[2]
    return total


def is_cut(edges, source, sink, removed, directed=True):
    """判断一组边是否构成源汇割：丢掉它们后源点再也到不了汇点。

    removed 给出边编号集合，必须都是边表里已有的编号。源汇相等报错。
    """
    directed = _check_directed(directed)
    _check_nodes(source, sink)
    arcs, _nodes = _normalize(edges, directed)
    known = set(arc[3] for arc in arcs)
    blocked = set()
    for eid in removed:
        if not _is_int(eid):
            raise GraphError("edge id must be an int")
        if eid not in known:
            raise GraphError("unknown edge id")
        blocked.add(eid)
    return sink not in reachable(arcs, source, blocked, directed)


def _canonical_min_cut(arcs, nodes, source, sink, directed):
    """朴素求最小割：枚举全部边子集，逐个丢掉后做连通性判断。

    在所有割得开的子集里，挑容量最小、割边最少、割边编号序列字典序最小、源侧
    集合最小的一组。边子集数随边数指数上涨，边一多就跑不动。
    """
    count = len(arcs)
    best = None
    for mask in range(1 << count):
        blocked = set()
        for i in range(count):
            if mask >> i & 1:
                blocked.add(arcs[i][3])
        reached = reachable(arcs, source, blocked, directed)
        if sink in reached:
            continue
        side = reached
        eids = tuple(_boundary(arcs, side, directed))
        key = (
            _capacity_of(arcs, side, directed),
            len(eids),
            eids,
            len(side),
            tuple(sorted(side)),
        )
        if best is None or key < best[0]:
            best = (key, side, eids)
    capacity = best[0][0]
    return {
        "capacity": capacity,
        "source_side": sorted(best[1]),
        "cut_edges": list(best[2]),
    }


def min_cut(edges, source, sink, directed=True):
    """朴素求源汇最小割，返回容量、源侧集合、割边编号列表。"""
    directed = _check_directed(directed)
    _check_nodes(source, sink)
    arcs, nodes = _normalize(edges, directed)
    return _canonical_min_cut(arcs, nodes, source, sink, directed)


def min_cut_value(edges, source, sink, directed=True):
    """朴素求源汇最小割的容量，只返回那个数。"""
    return min_cut(edges, source, sink, directed)["capacity"]


def feasible_cut(edges, source, sink, capacity, directed=True):
    """判断给定容量下有没有不超过该容量的割。

    有就返回那一组最小的割（容量、源侧集合、割边编号），没有就返回空。
    这里同样走枚举边子集的老路。
    """
    limit = _check_capacity(capacity)
    best = min_cut(edges, source, sink, directed)
    if best["capacity"] <= limit:
        return best
    return None


def global_min_cut_value(edges):
    """无向图的全局最小割容量：枚举所有非空真子集当源侧，取跨越容量最小者。

    只按无向口径解释边表；点少于两个时报错。
    """
    arcs, nodes = _normalize(edges, False)
    order = sorted(nodes)
    if len(order) < 2:
        raise GraphError("need at least two nodes")
    best = None
    for mask in range(1 << len(order)):
        side = set()
        for i in range(len(order)):
            if mask >> i & 1:
                side.add(order[i])
        if not side or len(side) == len(order):
            continue
        cap = _capacity_of(arcs, side, False)
        if best is None or cap < best:
            best = cap
    return best


def edge_subset_count(edges):
    """朴素枚举边子集时，需要过一遍的子集总数。"""
    return 1 << len(list(edges))


class CutTools:
    """绑定一张图与一个口径的割工具，只有枚举边子集这一条路。

    求最小割、判断某组边是不是割、判断给定容量下有没有更小的割都提供方法，并
    累计枚举边子集的次数，供与最大流增广次数对照规模。
    """

    def __init__(self, edges, directed=True):
        self._directed = _check_directed(directed)
        self._arcs, self._nodes = _normalize(edges, directed)
        self._subset_count = 0

    def directed(self):
        """返回这张图的口径。"""
        return self._directed

    def reset_subset_count(self):
        """把枚举边子集计数清零。"""
        self._subset_count = 0

    def subset_count(self):
        """自上次清零以来累计枚举了多少个边子集。"""
        return self._subset_count

    def _count(self, n):
        """累计一次枚举若干个子集。"""
        self._subset_count += n

    def min_cut(self, source, sink):
        """朴素求最小割，枚举边子集，计数随边数指数上涨。"""
        _check_nodes(source, sink)
        self._count(1 << len(self._arcs))
        return _canonical_min_cut(
            self._arcs, self._nodes, source, sink, self._directed)

    def is_cut(self, source, sink, removed):
        """朴素判断某组边是不是割：丢掉后走一遍连通性。"""
        _check_nodes(source, sink)
        self._count(1)
        known = set(arc[3] for arc in self._arcs)
        blocked = set()
        for eid in removed:
            if eid not in known:
                raise GraphError("unknown edge id")
            blocked.add(eid)
        return sink not in reachable(
            self._arcs, source, blocked, self._directed)

    def feasible_cut(self, source, sink, capacity):
        """朴素判断给定容量下有没有不超过该容量的割。"""
        limit = _check_capacity(capacity)
        found = self.min_cut(source, sink)
        if found["capacity"] <= limit:
            return found
        return None
