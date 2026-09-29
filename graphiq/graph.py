"""graphiq 的现状实现：朴素全对可达，纯标准库，无外部依赖。

Graph 用邻接表存有向图，边可以带一个非负权重。现在能做的分析只有可达性：
reachable(src) 从单个源点做一次深度优先搜索，给出可达集合；reachable_all()
对每个节点各做一次，得到全对可达。除此之外没有别的分析能力。

对外能力：
  add_node(node)                 登记一个节点，重复登记不报错
  add_edge(u, v, weight=1.0)     加一条有向边，端点懒登记，同向覆盖
  nodes()                        全部节点，出现顺序
  edges()                        全部有向边 (u, v, weight)，按 u、v 升序
  has_node(node) / has_edge(u, v)
  weight(u, v)                   边的权重，无边返回 None
  neighbors(u)                   直接后继，按 v 升序
  reachable(src)                 沿有向边可达的节点集合，含 src 自身
  reachable_all()                全对可达 {节点: 可达集合}
"""


class UnknownNode(KeyError):
    """引用了未登记的节点时抛出。"""


class Graph:
    """有向图。

    邻接表 _adj 是节点到「后继 -> 权重」的映射。自环即 u 与 v 相等，
    允许存在；对可达性而言自环不改变结果，节点本来就可达自身。
    """

    def __init__(self, nodes=None, edges=None):
        self._adj = {}
        for node in nodes or ():
            self.add_node(node)
        for edge in edges or ():
            if len(edge) == 2:
                u, v = edge
                self.add_edge(u, v)
            else:
                u, v, weight = edge
                self.add_edge(u, v, weight)

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

    def add_edge(self, u, v, weight=1.0):
        """加一条 u 指向 v 的边，端点懒登记，同向重复加边按覆盖处理。"""
        self._check_weight(weight)
        self.add_node(u)
        self.add_node(v)
        self._adj[u][v] = weight

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
        """直接后继，按 v 升序。"""
        if u not in self._adj:
            raise UnknownNode(u)
        return sorted(self._adj[u])

    # -- 可达性 ----------------------------------------------------------

    def reachable(self, src):
        """从 src 出发沿有向边可达的节点集合，含 src 自身。"""
        if src not in self._adj:
            raise UnknownNode(src)
        seen = {src}
        stack = [src]
        while stack:
            u = stack.pop()
            for v in self._adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    def reachable_all(self):
        """全对可达：对每个节点各做一次搜索。

        这是现状下唯一的分析能力，复杂度随节点数线性放大，
        但结果直白：每个节点的可达集合单独算一遍，互不影响。
        """
        return {node: self.reachable(node) for node in self._adj}
