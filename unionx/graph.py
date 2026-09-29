"""unionx 的朴素连通判定实现（改造前的现状）。

现在整个库只有一条连通判定路径：登记节点、加无向边，查询两点是否连通时
从一端出发做一次广度优先遍历，走到另一端就算连通。没有并查集，没有路径
压缩，没有按秩合并，组件成员与组件数都是查询时现场推出来的，也没有撤销
回滚、带权关系与离线批量查询。

上面的那些见任务描述。
"""

from collections import deque


class UnknownNode(KeyError):
    """访问一个没有登记过的节点。"""

    def __init__(self, node):
        super().__init__(node)
        self.node = node


class NaiveUnionFind:
    """朴素连通判定：每次查询都现算一遍广度优先遍历。

    只维护邻接表本身，连通性与组件信息都不做增量维护。
    """

    def __init__(self):
        self._index = {}
        self._adj = {}
        self._edges = []
        self._edge_keys = set()

    def add_node(self, node):
        """登记一个孤立节点，重复登记为 no-op，返回该节点。"""
        if not self.has_node(node):
            self._index[node] = len(self._index)
            self._adj[node] = []
        return node

    def has_node(self, node):
        """节点是否登记过。"""
        return node in self._adj

    def nodes(self):
        """按登记顺序返回全部节点。"""
        return tuple(sorted(self._adj, key=self._index.__getitem__))

    def add_edge(self, a, b):
        """加一条无向边，任一端点未登记就抛 UnknownNode。"""
        self._require(a, b)
        key = self._edge_key(a, b)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append((a, b))
        self._adj[a].append(b)
        self._adj[b].append(a)

    def edges(self):
        """按加入顺序返回全部无向边。"""
        return tuple(self._edges)

    def connected(self, a, b):
        """a 与 b 是否连通；两点都登记过才能问，否则抛 UnknownNode。"""
        self._require(a, b)
        if a == b:
            return True
        return b in self._reach(a)

    def component_of(self, node):
        """node 所在组件的全部成员，按登记顺序，含 node 自己。"""
        self._require(node)
        members = self._reach(node)
        members.add(node)
        return tuple(sorted(members, key=self._index.__getitem__))

    def component_count(self):
        """当前组件个数，孤立节点各算一个。"""
        seen = set()
        count = 0
        for node in self.nodes():
            if node in seen:
                continue
            count += 1
            seen |= self._reach(node)
            seen.add(node)
        return count

    def component_sizes(self):
        """各组件大小，按组件中最先登记的节点顺序。"""
        seen = set()
        sizes = []
        for node in self.nodes():
            if node in seen:
                continue
            members = self._reach(node)
            members.add(node)
            seen |= members
            sizes.append(len(members))
        return tuple(sizes)

    def _reach(self, start):
        """从 start 出发能走到的其余节点集合，不含 start 自己。"""
        seen = {start}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for nxt in self._adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        seen.discard(start)
        return seen

    def _edge_key(self, a, b):
        """边的规范化键：按登记先后把两端点排定，便于去重。"""
        ia, ib = self._index[a], self._index[b]
        return (a, b) if ia <= ib else (b, a)

    def _require(self, *nodes):
        for node in nodes:
            if node not in self._adj:
                raise UnknownNode(node)
