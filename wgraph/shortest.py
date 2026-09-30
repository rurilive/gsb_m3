"""加权图的朴素最短路实现（改造前基线）。

图用邻接表存，add_edge 登记一条默认有向的带权边。单源最短路用最直白的
扫描法：每轮在尚未访问的点里线性找距离最小的一个，再用它松弛全部邻居，
点数为 N 时每轮要线性扫 N 个点，轮数为 N，代价随点数平方级上涨。
"""


class EdgeError(ValueError):
    """与边或权值有关的非法输入。"""


class UnknownNode(KeyError):
    """引用了图中不存在的节点。"""


class WeightedGraph:
    """带非负权的图，默认有向，权值须为整数且非负。"""

    def __init__(self, directed=True):
        self.directed = bool(directed)
        self._adj = {}
        self._edge_count = 0

    # ---- 构建 ----

    def add_node(self, node):
        if node not in self._adj:
            self._adj[node] = []
        return node

    def add_edge(self, u, v, weight):
        if not isinstance(weight, int) or isinstance(weight, bool):
            raise EdgeError("weight must be an int")
        if weight < 0:
            raise EdgeError("weight must be non-negative")
        self.add_node(u)
        self.add_node(v)
        self._adj[u].append((v, weight))
        if not self.directed:
            self._adj[v].append((u, weight))
        self._edge_count += 1

    def nodes(self):
        return list(self._adj.keys())

    def has_node(self, node):
        return node in self._adj

    def neighbors(self, node):
        if node not in self._adj:
            raise UnknownNode(node)
        return list(self._adj[node])

    def node_count(self):
        return len(self._adj)

    def edge_count(self):
        return self._edge_count

    # ---- 朴素最短路 ----

    def shortest_distances(self, source):
        """朴素扫描法求单源最短距离，返回点名字到距离的字典。"""
        if source not in self._adj:
            raise UnknownNode(source)
        nodes = list(self._adj.keys())
        dist = {}
        for node in nodes:
            dist[node] = None
        dist[source] = 0
        visited = set()
        while True:
            best = None
            best_d = None
            for node in nodes:
                if node in visited:
                    continue
                if dist[node] is None:
                    continue
                if best_d is None or dist[node] < best_d:
                    best = node
                    best_d = dist[node]
            if best is None:
                break
            visited.add(best)
            for other, weight in self._adj[best]:
                candidate = best_d + weight
                if dist[other] is None or candidate < dist[other]:
                    dist[other] = candidate
        return dist

    def shortest_predecessors(self, source):
        """朴素扫描法求前驱，返回点名字到其最短路前驱的字典，源点与前驱为空。"""
        if source not in self._adj:
            raise UnknownNode(source)
        nodes = list(self._adj.keys())
        dist = {}
        pred = {}
        for node in nodes:
            dist[node] = None
            pred[node] = None
        dist[source] = 0
        visited = set()
        while True:
            best = None
            best_d = None
            for node in nodes:
                if node in visited:
                    continue
                if dist[node] is None:
                    continue
                if best_d is None or dist[node] < best_d:
                    best = node
                    best_d = dist[node]
            if best is None:
                break
            visited.add(best)
            for other, weight in self._adj[best]:
                candidate = best_d + weight
                if dist[other] is None or candidate < dist[other]:
                    dist[other] = candidate
                    pred[other] = best
        return pred

    def shortest_path(self, source, target):
        """朴素扫描法还原一条最短路径，返回点名字列表，不可达为空列表。"""
        if source not in self._adj:
            raise UnknownNode(source)
        if target not in self._adj:
            raise UnknownNode(target)
        pred = self.shortest_predecessors(source)
        if pred[target] is None and target != source:
            dist = self.shortest_distances(source)
            if dist[target] is None:
                return []
        path = [target]
        cursor = target
        while cursor != source:
            cursor = pred[cursor]
            if cursor is None:
                return []
            path.append(cursor)
        path.reverse()
        return path
