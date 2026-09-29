"""成环检查的朴素实现。

DagCheck 持有一个边集合，用深度优先遍历判断这些边是否构成环。
没有拓扑序、没有分层、没有最小环、没有增量能力。
"""


class DagCheck:
    """最朴素的成环检查器。

    只接受 (u, v) 形式的边，表示从 u 指向 v 的依赖关系。
    构造后调用 has_cycle() 判断边集合是否成环。
    """

    def __init__(self, edges=None):
        self._edges = list(edges) if edges else []

    def add_edge(self, u, v):
        """加入一条边。"""
        self._edges.append((u, v))

    def has_cycle(self):
        """用深度优先遍历判断是否存在环。"""
        adj = {}
        for u, v in self._edges:
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, [])
        color = {}
        for node in adj:
            color[node] = "white"
        for node in list(adj):
            if color[node] == "white":
                if self._dfs(node, adj, color):
                    return True
        return False

    def _dfs(self, node, adj, color):
        color[node] = "gray"
        for nxt in adj.get(node, []):
            if color[nxt] == "gray":
                return True
            if color[nxt] == "white":
                if self._dfs(nxt, adj, color):
                    return True
        color[node] = "black"
        return False

    @property
    def edges(self):
        """返回当前边集合的副本。"""
        return list(self._edges)
