"""flownet 的对偶流量工具（改造前的现状）。

现在只有一条朴素路：求最大流时，每轮从源点做一次广度搜索，找到一条到汇点的残
量路径就沿路推流，推完再重新搜下一条，直到再也找不到增广路为止；求最小割时，
枚举边表里所有边子集，逐个丢掉后看源点还能不能走到汇点，在能割开的子集里挑容
量最小、割边最少的那一组。结果都对，但每轮都要把整张残量网络重搜一遍，增广次
数与路径长度同阶，边一多、容量一大就明显变慢；最小割那一问更是随边数指数爆炸。

分层图上的多路增广、当前弧优化，以及由最大流残量图直接构造最小割的做法，见任
务描述。
"""

from collections import deque


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class GraphError(Erro):
    """网络参数或边表非法。"""


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


def _check_nodes(source, sink):
    """源汇相等是非法请求。"""
    if source == sink:
        raise GraphError("source and sink must differ")


def reachable(arcs, source, blocked):
    """丢掉 blocked 里的边后，从源点能走到的点集，广度优先的朴素遍历。"""
    adjacency = {}
    for u, v, _cap, eid in arcs:
        if eid in blocked:
            continue
        adjacency.setdefault(u, []).append(v)
    seen = {source}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for nxt in adjacency.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _boundary(arcs, side):
    """源侧集合与汇侧集合之间的那组边，返回按边编号升序的编号列表。"""
    eids = [eid for u, v, _cap, eid in arcs if u in side and v not in side]
    eids.sort()
    return eids


def _capacity_of(arcs, side):
    """源侧集合对应的割容量。"""
    total = 0
    for u, v, cap, _eid in arcs:
        if u in side and v not in side:
            total += cap
    return total


def _bfs_path(arcs, flow, source, sink):
    """在残量网络上做一次广度搜索，返回一条到汇点的增广路。

    增广路是一串 (边编号, 方向) 对，方向为一表示沿边正向推流，负一表示回退。
    找不到就返回空。
    """
    adjacency = {}
    for u, v, cap, eid in arcs:
        if cap - flow[eid] > 0:
            adjacency.setdefault(u, []).append((v, eid, 1))
        if flow[eid] > 0:
            adjacency.setdefault(v, []).append((u, eid, -1))
    previous = {source: None}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        if node == sink:
            break
        for nxt, eid, sign in adjacency.get(node, ()):
            if nxt not in previous:
                previous[nxt] = (node, eid, sign)
                queue.append(nxt)
    if sink not in previous:
        return []
    path = []
    cursor = sink
    while previous[cursor] is not None:
        node, eid, sign = previous[cursor]
        path.append((eid, sign))
        cursor = node
    path.reverse()
    return path


class FlowNetwork(object):
    """一张有向容量网络，记录源点、汇点与各边容量，允许平行边，禁止自环。

    增广维持在内部流量表上，调用 augment_once 每轮只推一条增广路。
    """

    def __init__(self, edges):
        self._arcs, self._nodes = _normalize(edges)
        self._flow = {}
        self.reset_flow()

    def reset_flow(self):
        """把所有边上的流量清零。"""
        self._flow = dict((eid, 0) for _u, _v, _cap, eid in self._arcs)

    def nodes(self):
        """登记过的节点，按字典序给出。"""
        return sorted(self._nodes)

    def edges(self):
        """全部边，按加入顺序给出，四元组起点、终点、容量、边编号。"""
        return list(self._arcs)

    def edge_count(self):
        """边数。"""
        return len(self._arcs)

    def flow_of(self, eid):
        """某条边当前流量。"""
        return self._flow[eid]

    def flows(self):
        """各边流量，按边编号升序给出 (边编号, 流量) 对。"""
        return sorted(self._flow.items())

    def value(self, source):
        """当前网络的流量值：源点上的净流出。"""
        out = 0
        into = 0
        for u, v, _cap, eid in self._arcs:
            if u == source:
                out += self._flow[eid]
            if v == source:
                into += self._flow[eid]
        return out - into

    def augment_once(self, source, sink):
        """朴素推进一次增广：广搜找一条增广路，沿路推流。

        返回这次推流推了多少；找不到增广路返回零。
        """
        _check_nodes(source, sink)
        path = _bfs_path(self._arcs, self._flow, source, sink)
        if not path:
            return 0
        bottleneck = None
        for eid, sign in path:
            residual = self._residual_of(eid, sign)
            if bottleneck is None or residual < bottleneck:
                bottleneck = residual
        for eid, sign in path:
            self._flow[eid] += bottleneck if sign == 1 else -bottleneck
        return bottleneck

    def _residual_of(self, eid, sign):
        """某条边沿给定方向还能推多少。"""
        cap = None
        for _u, _v, capacity, edge_id in self._arcs:
            if edge_id == eid:
                cap = capacity
                break
        if sign == 1:
            return cap - self._flow[eid]
        return self._flow[eid]

    def reachable_from(self, source):
        """残量网络上从源点出发可达的节点集。"""
        blocked = set()
        residual = []
        for u, v, cap, eid in self._arcs:
            if cap - self._flow[eid] > 0:
                residual.append((u, v, cap, eid))
            if self._flow[eid] > 0:
                residual.append((v, u, cap, eid))
        return reachable(residual, source, blocked)

    def copy(self):
        """复制一张结构相同、流量清零的网络。"""
        return FlowNetwork(self._arcs)


class _FlowResult(object):
    """一次最大流计算的结果。"""

    def __init__(self, value, augmentations, flows):
        self.value = value
        self.augmentations = augmentations
        self.flows = flows

    def __repr__(self):
        return "FlowResult(value=%r, augmentations=%r)" % (
            self.value, self.augmentations)


def max_flow(edges, source, sink):
    """用朴素方法求最大流。

    反复在残量网络上广搜一条增广路并沿路推流，直到找不到为止。
    返回结果对象的 value 是最大流值，augmentations 是走过的增广路条数，
    flows 是各边最终流量，按边编号升序给出的 (边编号, 流量) 列表。
    """
    _check_nodes(source, sink)
    network = FlowNetwork(edges)
    augmentations = 0
    while network.augment_once(source, sink) > 0:
        augmentations += 1
    return _FlowResult(network.value(source), augmentations, network.flows())


def _canonical_min_cut(arcs, source, sink):
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
        reached = reachable(arcs, source, blocked)
        if sink in reached:
            continue
        side = reached
        eids = tuple(_boundary(arcs, side))
        key = (
            _capacity_of(arcs, side),
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


def min_cut(edges, source, sink):
    """朴素求最小割，返回容量、源侧集合、割边编号列表。"""
    _check_nodes(source, sink)
    arcs, _nodes = _normalize(edges)
    return _canonical_min_cut(arcs, source, sink)


def min_cut_value(edges, source, sink):
    """朴素求最小割的容量，只返回那个数。"""
    return min_cut(edges, source, sink)["capacity"]


def is_cut(edges, source, sink, removed):
    """判断一组边是否构成源汇割：丢掉它们后源点再也到不了汇点。

    removed 给出边编号集合，必须都是边表里已有的编号。源汇相等报错。
    """
    _check_nodes(source, sink)
    arcs, _nodes = _normalize(edges)
    known = set(arc[3] for arc in arcs)
    blocked = set()
    for eid in removed:
        if not _is_int(eid):
            raise GraphError("edge id must be an int")
        if eid not in known:
            raise GraphError("unknown edge id")
        blocked.add(eid)
    return sink not in reachable(arcs, source, blocked)


def feasible_cut(edges, source, sink, capacity):
    """判断给定容量下有没有不超过该容量的割。

    有就返回那一组最小的割（容量、源侧集合、割边编号），没有就返回空。
    这里同样走枚举边子集的老路。
    """
    limit = _check_capacity(capacity)
    best = min_cut(edges, source, sink)
    if best["capacity"] <= limit:
        return best
    return None


def edge_subset_count(edges):
    """朴素枚举边子集时，需要过一遍的子集总数。"""
    return 1 << len(list(edges))


class FlowTools(object):
    """绑定一张图与源汇的流量工具，只有单路增广与枚举子集这两条老路。

    求最大流、求最小割、判断某组边是不是割、判断给定容量下有没有割都提供方法，
    并累计单路增广次数与枚举边子集的次数，供与分层多路增广对照规模。
    """

    def __init__(self, edges, source, sink):
        _check_nodes(source, sink)
        self._arcs, self._nodes = _normalize(edges)
        self._source = source
        self._sink = sink
        self._augment_count = 0
        self._subset_count = 0

    def source(self):
        """源点。"""
        return self._source

    def sink(self):
        """汇点。"""
        return self._sink

    def reset_augment_count(self):
        """把单路增广次数清零。"""
        self._augment_count = 0

    def reset_subset_count(self):
        """把枚举边子集次数清零。"""
        self._subset_count = 0

    def augment_count(self):
        """自上次清零以来累计走了多少条增广路。"""
        return self._augment_count

    def subset_count(self):
        """自上次清零以来累计枚举了多少个边子集。"""
        return self._subset_count

    def max_flow(self):
        """朴素求最大流，单路增广，增广次数随路径长度上涨。"""
        network = FlowNetwork(self._arcs)
        augmentations = 0
        while network.augment_once(self._source, self._sink) > 0:
            augmentations += 1
        self._augment_count += augmentations
        return _FlowResult(
            network.value(self._source), augmentations, network.flows())

    def min_cut(self):
        """朴素求最小割，枚举边子集，计数随边数指数上涨。"""
        self._subset_count += 1 << len(self._arcs)
        return _canonical_min_cut(self._arcs, self._source, self._sink)

    def is_cut(self, removed):
        """朴素判断某组边是不是割：丢掉后走一遍连通性。"""
        known = set(arc[3] for arc in self._arcs)
        blocked = set()
        for eid in removed:
            if not _is_int(eid):
                raise GraphError("edge id must be an int")
            if eid not in known:
                raise GraphError("unknown edge id")
            blocked.add(eid)
        return self._sink not in reachable(self._arcs, self._source, blocked)

    def feasible_cut(self, capacity):
        """朴素判断给定容量下有没有不超过该容量的割。"""
        limit = _check_capacity(capacity)
        found = self.min_cut()
        if found["capacity"] <= limit:
            return found
        return None
