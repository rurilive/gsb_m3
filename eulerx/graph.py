"""eulerx 的朴素基线实现（改造前）。

一张多重图，顶点用可比较的整数编号，无向边与有向边分别用列表逐条累积，
允许自环与平行边。这一层里所有一笔画问题都只靠枚举全部边顺序的排列、再逐条
检查首尾是否相接且每条边恰好走一次，阶乘的量级；判断可行性也靠尝试排列或
反复回溯。结果正确但边数一多就跑不动。对外只有模块级函数，不保存任何跨调用
的状态。
"""

import itertools


class EulerError(Exception):
    """eulerx 的错误基类，遇到非法输入时统一抛出它或它的子类。"""


class UnknownVertexError(EulerError):
    """引用了未登记的顶点时抛出。"""


class EmptyEdgeError(EulerError):
    """图里一条边都没有时抛出。"""


class _Graph:
    """内层实现：以边列表保存一张多重图。

    无向边与有向边分开存。无向图用 undirected，有向图用 directed，
    两种图不混用。
    """

    def __init__(self, directed):
        self._directed = directed
        self._undirected = []
        self._directed_edges = []
        self._vertices = set()

    # -- 建图 ------------------------------------------------------------

    def _touch(self, vertex):
        if vertex is None:
            raise EulerError("顶点不能为空")
        self._vertices.add(vertex)

    def add_vertex(self, vertex):
        """登记一个孤立顶点。"""
        self._touch(vertex)

    def add_edge(self, u, v):
        """加一条无向边，允许自环与平行边。"""
        if self._directed:
            raise EulerError("这是一张有向图，请用 add_arc")
        self._touch(u)
        self._touch(v)
        self._undirected.append((u, v))

    def add_arc(self, u, v):
        """加一条有向边 u 指向 v，允许自环与平行边。"""
        if not self._directed:
            raise EulerError("这是一张无向图，请用 add_edge")
        self._touch(u)
        self._touch(v)
        self._directed_edges.append((u, v))

    # -- 结构查询 --------------------------------------------------------

    def is_directed(self):
        return self._directed

    def vertices(self):
        """全部顶点，升序。"""
        return sorted(self._vertices)

    def undirected_edges(self):
        """全部无向边，按 (较小端点, 较大端点) 规整后升序，保留平行边。"""
        normalized = []
        for u, v in self._undirected:
            normalized.append((u, v) if u <= v else (v, u))
        normalized.sort()
        return normalized

    def directed_edges(self):
        """全部有向边，按 (尾, 头) 升序，保留平行边。"""
        return sorted(self._directed_edges)

    def _edges(self):
        return self._directed_edges if self._directed else self._undirected

    def degree(self, vertex=None):
        """无向图中某点的度；不给顶点时返回度字典。自环两端各计一次。"""
        if self._directed:
            raise EulerError("有向图没有无向度")
        result = {node: 0 for node in self._vertices}
        for u, v in self._undirected:
            result[u] = result.get(u, 0) + 1
            result[v] = result.get(v, 0) + 1
        if vertex is None:
            return result
        if vertex not in result:
            raise UnknownVertexError("顶点不存在：%r" % (vertex,))
        return result[vertex]

    def odd_degree_vertices(self):
        """全部奇度点，升序。"""
        degrees = self.degree()
        return sorted(node for node, d in degrees.items() if d % 2 == 1)

    def in_out_degree(self):
        """有向图的入度出度字典：返回 (入度, 出度)。"""
        if not self._directed:
            raise EulerError("无向图没有入度出度")
        indeg = {node: 0 for node in self._vertices}
        outdeg = {node: 0 for node in self._vertices}
        for u, v in self._directed_edges:
            outdeg[u] = outdeg.get(u, 0) + 1
            indeg[v] = indeg.get(v, 0) + 1
        return indeg, outdeg


def make_undirected():
    """建一张空的朴素无向多重图。"""
    return _Graph(directed=False)


def make_directed():
    """建一张空的朴素有向多重图。"""
    return _Graph(directed=True)


def _require_edges(graph):
    """确认图里至少有一条边，否则按统一口径抛 EmptyEdgeError。"""
    if not graph._edges():
        raise EmptyEdgeError("空图没有一笔画问题可解")


def _connected_over_edges(adjacency, vertices):
    """检查承载边的顶点是否在忽略方向下连成一片。"""
    carriers = [v for v in vertices if adjacency.get(v)]
    if not carriers:
        return True
    seen = {carriers[0]}
    stack = [carriers[0]]
    while stack:
        node = stack.pop()
        for other in adjacency.get(node, ()):
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return all(v in seen for v in carriers)


def _undirected_adjacency(graph):
    """无向边的邻接表，忽略方向。"""
    adjacency = {v: [] for v in graph.vertices()}
    for u, v in graph._undirected:
        adjacency.setdefault(u, []).append(v)
        adjacency.setdefault(v, []).append(u)
    return adjacency


def has_euler_path_undirected(graph):
    """无向图是否存在欧拉路径：承载边的部分连通，且奇度点个数为零或二。"""
    _require_edges(graph)
    odd = graph.odd_degree_vertices()
    if len(odd) not in (0, 2):
        return False
    return _connected_over_edges(_undirected_adjacency(graph), graph.vertices())


def has_euler_circuit_undirected(graph):
    """无向图是否存在欧拉回路：承载边的部分连通，且没有奇度点。"""
    _require_edges(graph)
    if graph.odd_degree_vertices():
        return False
    return _connected_over_edges(_undirected_adjacency(graph), graph.vertices())


def enumerate_edge_orders(graph):
    """枚举全部边序（边下标的排列），阶乘量级。"""
    return itertools.permutations(range(len(graph._edges())))


def naive_edge_order_check_count(graph):
    """朴素路径枚举要检查的边序总数，即边数的阶乘。"""
    return _factorial(len(graph._edges()))


def _factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def _grow_undirected(edges, order, path, start):
    """按边序把无向路径一段段接上；接不上就返回 None。

    无向边走哪一头都行；无起点时第一条边从较小端点起步，保证口径一致。
    """
    for index in order:
        u, v = edges[index]
        if not path:
            if start is None:
                path = [u, v] if u <= v else [v, u]
            elif u == start:
                path = [u, v]
            elif v == start:
                path = [v, u]
            else:
                return None
            continue
        last = path[-1]
        if u == last:
            path = path + [v]
        elif v == last:
            path = path + [u]
        else:
            return None
    return path if path else None


def _grow_directed(edges, order, path, start):
    """按边序把有向路径一段段接上；方向对不上就返回 None。"""
    for index in order:
        u, v = edges[index]
        if not path:
            if start is not None and u != start:
                return None
            path = [u, v]
            continue
        if path[-1] != u:
            return None
        path = path + [v]
    return path if path else None


def _order_to_vertices(graph, order, start=None):
    """按边序拼出顶点序列；前后两条边首尾不相接就返回 None。"""
    edges = graph._edges()
    if graph._directed:
        return _grow_directed(edges, order, [], start)
    return _grow_undirected(edges, order, [], start)


def naive_euler_path_undirected(graph, start=None):
    """朴素求一条欧拉路径：枚举全部边序，逐个检查首尾相接。

    返回顶点序列，取字典序最小的那一条；不存在时返回 None。给了起点就只认
    以该点起步的路径。
    """
    if not graph._undirected:
        return None
    best = None
    for order in enumerate_edge_orders(graph):
        path = _order_to_vertices(graph, order, start)
        if path is None:
            continue
        if best is None or path < best:
            best = path
    return best


def naive_euler_circuit_undirected(graph, start=None):
    """朴素求一条欧拉回路：枚举全部边序，逐个检查首尾相接且回到起点。

    返回顶点序列，取字典序最小的那一条；不存在时返回 None。
    """
    if not graph._undirected:
        return None
    best = None
    for order in enumerate_edge_orders(graph):
        path = _order_to_vertices(graph, order, start)
        if path is None or path[0] != path[-1]:
            continue
        if best is None or path < best:
            best = path
    return best


def naive_euler_path_directed(graph, start=None):
    """朴素求一条有向欧拉路径：枚举全部边序，逐个检查首尾相接且方向一致。

    返回顶点序列，取字典序最小的那一条；不存在时返回 None。
    """
    if not graph._directed_edges:
        return None
    best = None
    for order in enumerate_edge_orders(graph):
        path = _order_to_vertices(graph, order, start)
        if path is None:
            continue
        if best is None or path < best:
            best = path
    return best


def has_euler_path_directed(graph):
    """有向图是否存在欧拉路径：承载边的部分在忽略方向下连通，且至多一个点
    出度比入度大一、至多一个点入度比出度大一，其余入度等于出度。"""
    _require_edges(graph)
    indeg, outdeg = graph.in_out_degree()
    plus = [v for v in graph.vertices() if outdeg.get(v, 0) - indeg.get(v, 0) == 1]
    minus = [v for v in graph.vertices() if indeg.get(v, 0) - outdeg.get(v, 0) == 1]
    for v in graph.vertices():
        diff = outdeg.get(v, 0) - indeg.get(v, 0)
        if diff not in (-1, 0, 1):
            return False
    if len(plus) > 1 or len(minus) > 1 or len(plus) != len(minus):
        return False
    adjacency = {v: [] for v in graph.vertices()}
    for u, v in graph._directed_edges:
        adjacency.setdefault(u, []).append(v)
        adjacency.setdefault(v, []).append(u)
    return _connected_over_edges(adjacency, graph.vertices())


def chain_count(texts):
    """按朴素回溯把字符串排成一列，使相邻两个首尾相接，返回可行的排列个数。

    相同字符串算不同的牌，按位置计数。
    """
    items = list(texts)
    used = [False] * len(items)
    total = [0]

    def backtrack(last):
        if all(used):
            total[0] += 1
            return
        for i, item in enumerate(items):
            if used[i]:
                continue
            if last is None or last[-1] == item[0]:
                used[i] = True
                backtrack(item)
                used[i] = False

    backtrack(None)
    return total[0]


def itoa(index):
    """把整数编号转成一个大写字母名字，便于人工阅读顶点序列。

    零号记 A，二十五号记 Z，二十六号记 AA，按双射计数进位。
    """
    letters = []
    value = index + 1
    while value > 0:
        value, rem = divmod(value - 1, 26)
        letters.append(chr(ord("A") + rem))
    return "".join(reversed(letters))
