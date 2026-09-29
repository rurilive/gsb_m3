"""graphex.matrix: 无权邻接矩阵连通性工具。

现有实现只做一件事：在无权图上判断两点是否连通。每条边的遍历代价
视为相同的单位代价，不记录边长，也不产出最短距离或路径。
"""


class GraphError(Exception):
    """graphex 的业务异常基类。"""


class UnknownNode(GraphError):
    """引用了未登记的节点。"""


class ReachMatrix:
    """无权邻接矩阵，用于判断节点间的连通性。

    邻接矩阵按登记顺序给节点分配下标，边以 0 或 1 记录，无向图双向置位。
    连通判断走单位代价的广度优先遍历，只回答可达与否，不比较路径长短。
    """

    def __init__(self, nodes=None):
        self._index = {}
        self._names = []
        self._rows = []
        if nodes is not None:
            for name in nodes:
                self.add_node(name)

    def add_node(self, name):
        if not isinstance(name, str) or not name:
            raise GraphError("节点名必须是非空字符串")
        if name in self._index:
            return
        self._index[name] = len(self._names)
        self._names.append(name)
        for row in self._rows:
            row.append(0)
        self._rows.append([0] * len(self._names))

    def has_node(self, name):
        return name in self._index

    def nodes(self):
        return list(self._names)

    def add_edge(self, a, b):
        ia = self._require(a)
        ib = self._require(b)
        self._rows[ia][ib] = 1
        self._rows[ib][ia] = 1

    def has_edge(self, a, b):
        ia = self._require(a)
        ib = self._require(b)
        return bool(self._rows[ia][ib])

    def reached_from(self, start):
        start_i = self._require(start)
        seen = [False] * len(self._names)
        reached = []
        seen[start_i] = True
        queue = [start_i]
        head = 0
        while head < len(queue):
            i = queue[head]
            head += 1
            reached.append(self._names[i])
            for j in range(len(self._names)):
                if self._rows[i][j] and not seen[j]:
                    seen[j] = True
                    queue.append(j)
        return sorted(reached)

    def connected(self, a, b):
        self._require(b)
        return b in self.reached_from(a)

    def _require(self, name):
        if name not in self._index:
            raise UnknownNode(name)
        return self._index[name]
