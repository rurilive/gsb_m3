"""shortestpath.dijkstra：带非负权图的单源最短路（改造前的朴素实现）。

现状做法：每轮在尚未确定的结点里线性扫描一遍找出当前距离最小者，把它
确定下来，再逐边把它所有邻居松驰一遍；如此往复直到没有可确定的结点。
路径从源点逐段记住前驱后回溯拼出。找最小这一步整体线性扫描，单次求解
的代价随结点数平方增长。

这套做法结果是对的，规模小时一眼能看穿，但一轮找最小就把还没确定的
结点全部走一遍，轮数又随结点数增长，结点一多就顶不住了。负权边、
非整数权重、终点不在图中、非法源点，统一抛异常快速失败，绝不悄悄
兜底也不擅自改小。不可达的结点在距离表里取不到键，用是否在表中出现
这一口径表示；它们也没有可回溯的路径，取路径时同样快速失败。
"""


class ShortestPathError(Exception):
    """shortestpath 全部异常的共同基类。"""


class NodeNotFoundError(ShortestPathError):
    """源点或终点不在图中，属于调用方非法输入。"""


class NegativeWeightError(ShortestPathError):
    """出现了负权边，不满足本模块的前提。"""


class UnreachableNodeError(ShortestPathError):
    """对不可达结点下达了无法定义结果的操作。"""


class NaiveGraph:
    """带非负权有向图与单源最短路（基线：每轮线性找最小）。

    构造参数 edges 是一串三元组，每项为 (起点, 终点, 权重)，起点与终点
    是任意可哈希结点，权重是非负实数。平行边（同一对起终点出现多次）
    按最小权保留；指向自身的自环不参与松驰；权为零的边照常参与。孤点
    不会出现在 edges 里，可经 add_node 显式登记。

    求解时每轮在尚未确定的结点里线性扫描找出距离最小者，再逐边松驰它
    的邻居；这一轮找最小把未确定结点整体走了一遍，代价随结点数平方级
    增长。distances 返回从源点到各可达点的最短距离，dict 里取不到的键
    即不可达点；paths 在距离表之上按前驱回溯拼出路径。lookups 统计
    solve 期间在未确定集合里比较过的次数，暴露线性找最小的开销。
    """

    def __init__(self, edges):
        self._adj = {}
        self._order = []
        if edges is None:
            raise ShortestPathError("edges must be an iterable, got None")
        for edge in edges:
            try:
                u, v, w = edge
            except (TypeError, ValueError):
                raise ShortestPathError("edge must be a triple: %r" % (edge,))
            self._check_weight(w)
            self.add_node(u)
            self.add_node(v)
            cur = self._adj[u].get(v)
            if cur is None or w < cur:
                self._adj[u][v] = w

    def _check_weight(self, weight):
        """权重必须是非负实数；排除布尔与负数。"""
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise NegativeWeightError("weight must be a real number, got %r"
                                      % (type(weight).__name__,))
        if weight < 0:
            raise NegativeWeightError("weight must be non-negative, got %r"
                                      % (weight,))

    def add_node(self, node):
        """显式登记一个孤点（没有入边也没有出边）。"""
        if node not in self._adj:
            self._adj[node] = {}
            self._order.append(node)
        return node

    def nodes(self):
        """图中全部结点，顺序按首次出现的先后固定。"""
        return list(self._order)

    def size(self):
        """结点个数。"""
        return len(self._order)

    @staticmethod
    def _pick_min(remaining, dist):
        """线性扫描出距离最小的未确定结点。

        基线做法：把 remaining 里每一个候选都看一遍，逐个比较距离取最小。
        这一步整体线性，且每一轮都要重来一遍。probes 记下这一轮比了几个。
        """
        best = None
        best_d = None
        probes = 0
        for node in remaining:
            probes += 1
            d = dist.get(node)
            if d is None:
                continue
            if best is None or d < best_d:
                best = node
                best_d = d
        return best, best_d, probes

    def _solve(self, source):
        """朴素的单源最短路。

        每轮线性找出未确定结点里距离最小者，确定它，再逐边松驰其邻居。
        返回距离表、前驱表与找最小比较次数的统计。
        """
        if source not in self._adj:
            raise NodeNotFoundError("source %r not in graph" % (source,))
        dist = {source: 0}
        prev = {}
        remaining = list(self._order)
        lookups = 0
        while remaining:
            node, cur, probes = self._pick_min(remaining, dist)
            lookups += probes
            if node is None:
                # 剩下的结点都不可达，全部放在原地不再确定
                break
            remaining.remove(node)
            for nxt, weight in self._adj[node].items():
                if nxt == node:
                    continue  # 自环不参与松驰
                cand = cur + weight
                if nxt not in dist or cand < dist[nxt]:
                    dist[nxt] = cand
                    prev[nxt] = node
        return dist, prev, lookups

    def distances(self, source):
        """从 source 出发到各可达点的最短距离，返回 dict 的拷贝。

        dict 里取不到的键即不可达点。每次调用都重新求解，结果只由本次
        输入决定，不残留上一轮的痕迹。
        """
        dist, _prev, _lookups = self._solve(source)
        return dict(dist)

    def paths(self, source):
        """从 source 出发到各可达点的最短路径，返回 dict 的拷贝。

        每条路径是结点列表，首项为源点、末项为该点，按前驱逐段回溯拼出。
        源点自身的路径就是只含源点一项的列表。不可达点不会出现在结果里。
        每次调用独立求解，与 distances 对同一源点逐项一致。
        """
        dist, prev, _lookups = self._solve(source)
        out = {source: [source]}
        for node in dist:
            if node == source:
                continue
            route = [node]
            walk = node
            while walk in prev:
                walk = prev[walk]
                route.append(walk)
            route.reverse()
            out[node] = route
        return out

    def path(self, source, target):
        """从 source 到 target 的一条最短路径，结点列表。

        源点自身的路径就是只含源点一项的列表。target 不在图中，或者
        可达点里没有 target，都快速失败。
        """
        if source not in self._adj:
            raise NodeNotFoundError("source %r not in graph" % (source,))
        if target not in self._adj:
            raise NodeNotFoundError("target %r not in graph" % (target,))
        if target == source:
            return [source]
        all_paths = self.paths(source)
        if target not in all_paths:
            raise UnreachableNodeError("target %r is unreachable from %r"
                                       % (target, source))
        return all_paths[target]

    def unreachable(self, source):
        """从 source 出发不可达的结点列表，按结点登记顺序固定。"""
        if source not in self._adj:
            raise NodeNotFoundError("source %r not in graph" % (source,))
        reach = set(self.paths(source))
        return [node for node in self._order if node not in reach]

    def lookups(self, source):
        """本次求解在未确定集合里的线性比较次数。

        基线做法：每一轮找最小都把未确定结点整体线性扫一遍，所以结点数
        为 n 的连通图一共比 n 加 n 减一到一，即二分之一 n 乘 n 加一，随
        结点数平方级增长。只记最近一次求解，重复调用各自独立重算。
        """
        _dist, _prev, lookups = self._solve(source)
        return lookups

    def stats(self, source):
        """结点、边与最近一次求解访问量的快照，独立 dict，改它不影响实例。"""
        dist, _prev, lookups = self._solve(source)
        return {
            "nodes": len(self._order),
            "edges": sum(len(nbrs) for nbrs in self._adj.values()),
            "reachable": len(dist),
            "lookups": lookups,
        }
