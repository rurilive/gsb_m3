"""stoerwagner 的全局最小割工具（改造前的现状）。

现在只有朴素路：求无向图的全局最小割时，对图上每一对点都从头跑一遍最大流，
把所有点对里最小的那个最大流值当作全局最小割；另一条老路是把所有点集切分逐
个枚举出来，算跨越权重取最小。两条路结果都对，但点对数是点数的平方，每一对
点还要重头把最大流重新算一遍，点一多就慢得刺眼，合并操作、最大邻接搜索扩展
这类做法一概没有。反复用最大邻接搜索扩展出当前最后两点、记下最后一点到其余
点的割权、再把最后两点合并这类做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class GraphError(Erro):
    """图参数或边表非法。"""


class CutError(Erro):
    """割请求本身不合法。"""


def _is_int(value):
    """是不是真正的整数，布尔值不算。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_weight(value):
    """边权必须是非负整数。"""
    if not _is_int(value):
        raise GraphError("weight must be an int")
    if value < 0:
        raise GraphError("weight must not be negative")
    return value


def normalize_edges(edges):
    """把无向边表整理成定长四元组，顺带校验并收集点集。

    每条边写成起点、终点、边权、边编号；只给三元组时边编号取它在表里的位置。
    自环直接拒绝，边权必须非负，边编号不得重复。返回边表与点集。
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
            raise GraphError("each edge is start, end, weight, id")
        u = edge[0]
        v = edge[1]
        weight = _check_weight(edge[2])
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
        arcs.append((u, v, weight, eid))
        nodes.add(u)
        nodes.add(v)
    return arcs, nodes


def _matrix(order, arcs):
    """把边表折成对称的邻接权重表，平行边的权重直接累加。

    无向边按正反两条有向弧各给一份容量处理，这样点对之间的最大流值就等于它
    们的上述口径最小割。
    """
    weights = {}
    for node in order:
        weights[node] = {}
    for u, v, weight, _eid in arcs:
        weights[u][v] = weights[u].get(v, 0) + weight
        weights[v][u] = weights[v].get(u, 0) + weight
    return weights


def _max_flow(weights, order, source, sink, counter):
    """朴素的增广路最大流：反复做广度优先搜索找一条增广路并推流。

    每推一次流给 counter 加一。weights 是邻接权重表，这里拷一份当残量网络用，
    不碰调用方的数据。
    """
    residual = {}
    for node in order:
        residual[node] = dict(weights[node])
    value = 0
    while True:
        parent = {source: None}
        queue = [source]
        head = 0
        while head < len(queue) and sink not in parent:
            node = queue[head]
            head += 1
            row = residual[node]
            for nxt in order:
                if nxt in parent:
                    continue
                if row.get(nxt, 0) > 0:
                    parent[nxt] = node
                    queue.append(nxt)
        if sink not in parent:
            break
        limit = None
        node = sink
        while parent[node] is not None:
            prev = parent[node]
            cap = residual[prev][node]
            limit = cap if limit is None else min(limit, cap)
            node = prev
        node = sink
        while parent[node] is not None:
            prev = parent[node]
            residual[prev][node] -= limit
            residual[node][prev] = residual[node].get(prev, 0) + limit
            node = prev
        value += limit
        counter[0] += 1
    return value


def _pairwise_value(arcs, nodes, counter):
    """对每一对点各跑一遍最大流，取所有点对里的最小流值。"""
    order = sorted(nodes)
    if len(order) < 2:
        raise CutError("need at least two nodes to cut")
    weights = _matrix(order, arcs)
    best = None
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            value = _max_flow(weights, order, order[i], order[j], counter)
            if best is None or value < best:
                best = value
    return best


def pairwise_min_cut_value(edges, counter=None):
    """逐对点跑最大流取最小，作为无向图的全局最小割值。

    counter 传进来一个单元素列表时会累计推流次数，供规模对照。点少于两个报错。
    """
    arcs, nodes = normalize_edges(edges)
    if counter is None:
        counter = [0]
    return _pairwise_value(arcs, nodes, counter)


def max_flow_value(edges, source, sink):
    """单次最大流：源点与汇点之间朴素增广，返回流值。源汇相等报错。"""
    if source == sink:
        raise CutError("source and sink must differ")
    arcs, nodes = normalize_edges(edges)
    order = sorted(nodes)
    if source not in nodes or sink not in nodes:
        return 0
    weights = _matrix(order, arcs)
    return _max_flow(weights, order, source, sink, [0])


def exhaustive_min_cut_value(edges):
    """枚举所有非空真切分算跨越权重取最小，小图上的独立印证口径。"""
    arcs, nodes = normalize_edges(edges)
    order = sorted(nodes)
    count = len(order)
    if count < 2:
        raise CutError("need at least two nodes to cut")
    best = None
    for mask in range(1, (1 << count) - 1):
        side = set()
        for i in range(count):
            if mask >> i & 1:
                side.add(order[i])
        total = 0
        for u, v, weight, _eid in arcs:
            if (u in side) != (v in side):
                total += weight
        if best is None or total < best:
            best = total
    return best


class MinCutTools:
    """绑定一张无向图的全局最小割工具，只有逐对点最大流这一条路。

    求全局最小割时对每一对点都从头跑一遍最大流，并累计推流次数供规模对照。
    """

    def __init__(self, edges):
        self._arcs, self._nodes = normalize_edges(edges)
        self._augment = 0

    def node_count(self):
        """返回图里的点数。"""
        return len(self._nodes)

    def reset_augment_count(self):
        """把推流计数清零。"""
        self._augment = 0

    def augment_count(self):
        """自上次清零以来累计推了多少次流。"""
        return self._augment

    def global_min_cut(self):
        """逐对点跑最大流取最小，推流次数随点数平方级别上涨。"""
        counter = [0]
        value = _pairwise_value(self._arcs, self._nodes, counter)
        self._augment += counter[0]
        return value

    def exhaustive_min_cut(self):
        """同一张图上用枚举切分的老路再算一遍，作为对照。"""
        return exhaustive_min_cut_value(self._arcs)
