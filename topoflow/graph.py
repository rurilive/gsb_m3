"""有向图的底层存储，纯标准库。

邻接表用 dict 维护，登记次序就是节点和边的次序；重复边只记一次。
图本身不管拓扑，排序动作都在 engine.py 里。
"""


class DiGraph:
    """有向图。

    nodes() 返回节点加入顺序，edges() 按源节点的加入顺序展开，
    successors() / predecessors() 也按登记顺序给出。
    """

    def __init__(self):
        self._out = {}   # node -> {succ: None}
        self._in = {}    # node -> {pred: None}

    def add_node(self, node):
        """登记一个节点，已存在返回 False。"""
        if node in self._out:
            return False
        self._out[node] = {}
        self._in[node] = {}
        return True

    def has_node(self, node):
        return node in self._out

    def add_edge(self, u, v):
        """加一条边，缺的节点自动补上；这条边已经在了返回 False。"""
        self.add_node(u)
        self.add_node(v)
        if v in self._out[u]:
            return False
        self._out[u][v] = None
        self._in[v][u] = None
        return True

    def remove_edge(self, u, v):
        """删一条边，边不在图里返回 False。"""
        if u not in self._out or v not in self._out[u]:
            return False
        del self._out[u][v]
        del self._in[v][u]
        return True

    def has_edge(self, u, v):
        return u in self._out and v in self._out[u]

    def nodes(self):
        """节点加入顺序。"""
        return list(self._out)

    def edges(self):
        """全部边，按源节点的加入顺序展开。"""
        return [(u, v) for u in self._out for v in self._out[u]]

    def successors(self, u):
        return list(self._out.get(u, ()))

    def predecessors(self, v):
        return list(self._in.get(v, ()))

    def out_degree(self, u):
        return len(self._out.get(u, ()))

    def in_degree(self, v):
        return len(self._in.get(v, ()))

    def node_count(self):
        return len(self._out)

    def edge_count(self):
        return sum(len(succ) for succ in self._out.values())
