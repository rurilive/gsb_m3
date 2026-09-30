"""centdecomp：树上路径统计的朴素实现（改造前基线）。

全部能力都建立在同一件事上：把每一对顶点之间的路径原样走一遍，再按目标
条件逐条判定。做法直白、结果正确，顶点一多就退化到平方量级。
"""


class CentdecompError(Exception):
    """所有 centdecomp 错误的公共基类。"""


class TreeError(CentdecompError):
    """树的形状或输入不合法。"""


class QueryError(CentdecompError):
    """查询参数不合法。"""


class Tree:
    """无向带权树：n 个顶点，若干条非负整数权的无向边。

    n 必须为正整数，否则抛 TreeError。顶点编号固定为 0 到 n-1。
    """

    def __init__(self, n):
        if not isinstance(n, int) or isinstance(n, bool):
            raise TreeError("n must be an int")
        if n < 1:
            raise TreeError("n must be >= 1")
        self._n = n
        self._adj = [[] for _ in range(n)]

    @property
    def n(self):
        """顶点个数。"""
        return self._n

    def add_edge(self, u, v, weight=1):
        """加一条 u-v 的无向边，权为非负整数。越界或权为负抛 TreeError。"""
        for node in (u, v):
            if not isinstance(node, int) or isinstance(node, bool):
                raise TreeError("vertex id must be an int")
            if node < 0 or node >= self._n:
                raise TreeError("vertex id out of range")
        if not isinstance(weight, int) or isinstance(weight, bool):
            raise TreeError("weight must be an int")
        if weight < 0:
            raise TreeError("weight must be >= 0")
        self._adj[u].append((v, weight))
        self._adj[v].append((u, weight))

    def neighbors(self, u):
        """顶点 u 的邻居列表，元素是 (邻居, 边长)。"""
        if u < 0 or u >= self._n:
            raise TreeError("vertex id out of range")
        return list(self._adj[u])

    def edges(self):
        """全部无向边，每条只出现一次，元素是 (u, v, weight)。"""
        seen = []
        for u in range(self._n):
            for v, w in self._adj[u]:
                if u < v:
                    seen.append((u, v, w))
        return seen

    def degree(self, u):
        """顶点 u 的度数。"""
        return len(self.neighbors(u))

    def path_distance(self, src, dst):
        """src 到 dst 沿唯一路径的边长之和，起点终点同一点时为 0。

        朴素做法：从 src 出发做一次深度优先搜索，找到 dst 就回传累计距离。
        """
        if src < 0 or src >= self._n or dst < 0 or dst >= self._n:
            raise TreeError("vertex id out of range")
        if src == dst:
            return 0
        stack = [(src, -1, 0)]
        while stack:
            node, parent, dist = stack.pop()
            if node == dst:
                return dist
            for nxt, w in self._adj[node]:
                if nxt != parent:
                    stack.append((nxt, node, dist + w))
        raise TreeError("tree is not connected")

    def all_pairs_distances(self):
        """所有无序点对 (i, j) 及其路径距离，i 小于 j，按字典序排列。

        这是基线最贵的一步：逐个点对各跑一次路径搜索。
        """
        out = []
        for i in range(self._n):
            for j in range(i + 1, self._n):
                out.append((i, j, self.path_distance(i, j)))
        return out

    def pair_count(self):
        """无序点对总数，即 n 取 2 的组合数。"""
        return self._n * (self._n - 1) // 2


def _check_query(tree, d):
    """查询参数校验：树要像样、距离要为非负整数。"""
    if not isinstance(tree, Tree):
        raise QueryError("tree must be a Tree")
    if not isinstance(d, int) or isinstance(d, bool):
        raise QueryError("distance must be an int")
    if d < 0:
        raise QueryError("distance must be >= 0")


def count_exact(tree, d):
    """距离恰好等于 d 的无序点对条数。

    朴素做法：枚举全部点对，逐对求路径距离再比较。
    """
    _check_query(tree, d)
    total = 0
    for _, _, dist in tree.all_pairs_distances():
        if dist == d:
            total += 1
    return total


def count_at_most(tree, d):
    """距离不超过 d 的无序点对条数。

    朴素做法：枚举全部点对，路径距离不大于 d 就记一笔。
    """
    _check_query(tree, d)
    total = 0
    for _, _, dist in tree.all_pairs_distances():
        if dist <= d:
            total += 1
    return total


def diameter(tree):
    """最远点对的长度与端点，返回三元组 (长度, 端点甲, 端点乙)。

    距离最大的点对可能不止一对，并列时取端点编号字典序最小的一对。单节点树
    返回 (0, 0, 0)。朴素做法同样要枚举全部点对。
    """
    _check_query(tree, 0)
    if tree.n == 1:
        return (0, 0, 0)
    best = None
    for i, j, dist in tree.all_pairs_distances():
        if best is None or dist > best[0]:
            best = (dist, i, j)
    return best


def enumerate_pair_visits(tree):
    """朴素做法要枚举的无序点对总条数，即 n 取 2 的组合数。"""
    if not isinstance(tree, Tree):
        raise QueryError("tree must be a Tree")
    return tree.pair_count()


__all__ = [
    "CentdecompError",
    "QueryError",
    "TreeError",
    "Tree",
    "count_exact",
    "count_at_most",
    "diameter",
    "enumerate_pair_visits",
]
