"""graphinc 的静态有向加权图现有实现，纯标准库，无外部依赖。

构造时一次建成邻接表，单源最短路按 Dijkstra 语义计算，结果按源点缓存在
内部；图建成之后不再变动，因此缓存不需要失效。权重约定为非负数值，
非负约束在加边处校验。

现有对外能力：
  add_node(node)                 登记一个节点，重复登记不报错
  nodes()                        全部节点，出现顺序
  edges()                        全部有向边 (u, v, weight)，按 u、v 升序
  has_node(node) / has_edge(u, v)
  weight(u, v)                   边的权重，无边返回 None
  neighbors(u)                   直接后继 (v, weight)，按 v 升序
  distances(src)                 单源最短距离，不可达记 math.inf
  shortest_path(src, dst)        (距离, 路径列表)，不可达为 (inf, [])
  reachable(src)                 可达节点集合，含源点自身
  topo_order()                   拓扑序，有环抛 CycleError
"""

import heapq
import math


class UnknownNode(KeyError):
    """引用了未登记的节点时抛出。"""


class CycleError(ValueError):
    """图中存在环时抛出。"""


class DirectedWeightedGraph:
    """静态有向加权图。

    邻接表 _adj 是节点到「后继 -> 权重」的映射。distances 的结果按源点缓存
    在 _dist_cache 中，静态图下缓存恒为有效。
    """

    def __init__(self, nodes=None, edges=None):
        self._adj = {}
        self._dist_cache = {}
        for node in nodes or ():
            self.add_node(node)
        for u, v, weight in edges or ():
            self._add_edge(u, v, weight)

    # -- 建图 ------------------------------------------------------------

    def add_node(self, node):
        """登记一个节点，重复登记不改动已有出边。"""
        if node is None:
            raise ValueError("node must not be None")
        if node not in self._adj:
            self._adj[node] = {}

    def _check_weight(self, weight):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError("weight must be a real number, got %r" % (weight,))
        if weight < 0:
            raise ValueError("weight must be non-negative, got %r" % (weight,))

    def _add_edge(self, u, v, weight):
        """建图期内部加边，覆盖同 (u, v) 上已有的权重。"""
        self._check_weight(weight)
        self.add_node(u)
        self.add_node(v)
        self._adj[u][v] = weight
        self._dist_cache.clear()

    # -- 结构查询 --------------------------------------------------------

    def nodes(self):
        return list(self._adj)

    def has_node(self, node):
        return node in self._adj

    def has_edge(self, u, v):
        return u in self._adj and v in self._adj[u]

    def edges(self):
        out = []
        for u in self._adj:
            for v in self._adj[u]:
                out.append((u, v, self._adj[u][v]))
        return sorted(out)

    def weight(self, u, v):
        """边 (u, v) 的权重，无边或端点不存在返回 None。"""
        if u not in self._adj:
            return None
        return self._adj[u].get(v)

    def neighbors(self, u):
        """直接后继 (v, weight)，按 v 升序。"""
        if u not in self._adj:
            raise UnknownNode(u)
        return [(v, self._adj[u][v]) for v in sorted(self._adj[u])]

    # -- 单源最短路 ------------------------------------------------------

    def distances(self, src):
        """Dijkstra 单源最短距离，不可达节点记 math.inf。

        结果按源点缓存；同一源点重复调用直接命中缓存。
        """
        if src not in self._adj:
            raise UnknownNode(src)
        cached = self._dist_cache.get(src)
        if cached is not None:
            return dict(cached)
        dist = {node: math.inf for node in self._adj}
        dist[src] = 0
        heap = [(0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v, w in self._adj[u].items():
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        self._dist_cache[src] = dict(dist)
        return dist

    def shortest_path(self, src, dst):
        """返回 (最短距离, 路径列表)，不可达时距离为 math.inf、路径为空。"""
        dist = self.distances(src)
        if dst not in dist:
            raise UnknownNode(dst)
        if math.isinf(dist[dst]):
            return math.inf, []
        # 反向重现一条最短路：从 dst 往前挑满足三角等式的边。
        path = [dst]
        cur = dst
        while cur != src:
            for u in self._adj:
                w = self._adj[u].get(cur)
                if w is None:
                    continue
                if dist[u] + w == dist[cur]:
                    path.append(u)
                    cur = u
                    break
            else:                       # pragma: no cover - 构造保证可达
                raise AssertionError("no predecessor on a shortest path")
        path.reverse()
        return dist[dst], path

    def reachable(self, src):
        """从 src 出发沿有向边可达的节点集合，含 src 自身。"""
        dist = self.distances(src)
        return {node for node, d in dist.items() if not math.isinf(d)}

    # -- 拓扑序 ----------------------------------------------------------

    def topo_order(self):
        """Kahn 拓扑排序，同层节点按字典序出队，结果确定。

        图中存在环时抛 CycleError。
        """
        indegree = {n: 0 for n in self._adj}
        for u in self._adj:
            for v in self._adj[u]:
                indegree[v] += 1
        heap = [n for n, d in indegree.items() if d == 0]
        heapq.heapify(heap)
        order = []
        while heap:
            u = heapq.heappop(heap)
            order.append(u)
            for v in sorted(self._adj[u]):
                indegree[v] -= 1
                if indegree[v] == 0:
                    heapq.heappush(heap, v)
        if len(order) != len(self._adj):
            raise CycleError("graph has a cycle")
        return order
