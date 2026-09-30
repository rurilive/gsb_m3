"""treehash：树同构判定与规范哈希的朴素实现（改造前基线）。

全部能力都建立在同一件事上：对两棵树的根各取子树，把一边的子树与另一边的
子树两两配对，尝试所有配对方式之后再递归下去；无根树先枚举重心当根，再对
每对重心做同样的递归比较。做法直白、结果正确，树一多就退化到平方甚至更高
量级，重心枚举还在外面又叠了一层。
"""


class TreehashError(Exception):
    """所有 treehash 错误的公共基类。"""


class TreeError(TreehashError):
    """树的形状或输入不合法。"""


class QueryError(TreehashError):
    """查询参数不合法。"""


class Tree:
    """无向简单树：n 个顶点，若干条无向边。

    n 必须为非负整数，零表示一棵没有任何顶点的空树。顶点编号固定为 0 到
    n-1。自环与重复边都不是树，加入时抛 TreeError。
    """

    def __init__(self, n):
        if not isinstance(n, int) or isinstance(n, bool):
            raise TreeError("n must be an int")
        if n < 0:
            raise TreeError("n must be >= 0")
        self._n = n
        self._adj = [[] for _ in range(n)]

    @property
    def n(self):
        """顶点个数。"""
        return self._n

    def add_edge(self, u, v):
        """加一条 u 到 v 的无向边。越界、自环或重复边抛 TreeError。"""
        for node in (u, v):
            if not isinstance(node, int) or isinstance(node, bool):
                raise TreeError("vertex id must be an int")
            if node < 0 or node >= self._n:
                raise TreeError("vertex id out of range")
        if u == v:
            raise TreeError("self loop is not allowed")
        if v in self._adj[u]:
            raise TreeError("duplicate edge is not allowed")
        self._adj[u].append(v)
        self._adj[v].append(u)

    def neighbors(self, u):
        """顶点 u 的邻居编号列表。"""
        self._check_vertex(u)
        return list(self._adj[u])

    def _check_vertex(self, u):
        if not isinstance(u, int) or isinstance(u, bool):
            raise TreeError("vertex id must be an int")
        if u < 0 or u >= self._n:
            raise TreeError("vertex id out of range")

    def degree(self, u):
        """顶点 u 的度数。"""
        return len(self.neighbors(u))

    def edges(self):
        """全部无向边，每条只出现一次，按字典序返回 (u, v)。"""
        out = []
        for u in range(self._n):
            for v in self._adj[u]:
                if u < v:
                    out.append((u, v))
        return sorted(out)

    def centroids(self):
        """全部重心编号，升序返回。空树返回空列表。

        朴素做法：对每个顶点，删掉它之后逐块做一次搜索求连通块大小，最大的
        那块不超过顶点数一半时它就是重心。每个顶点都要重新搜一遍全树。
        """
        if self._n == 0:
            return []
        result = []
        total = self._n
        for center in range(total):
            seen = [False] * total
            seen[center] = True
            largest = 0
            for start in self._adj[center]:
                if seen[start]:
                    continue
                size = 0
                seen[start] = True
                stack = [start]
                while stack:
                    node = stack.pop()
                    size += 1
                    for nxt in self._adj[node]:
                        if not seen[nxt]:
                            seen[nxt] = True
                            stack.append(nxt)
                if size > largest:
                    largest = size
            if largest * 2 <= total:
                result.append(center)
        return result


def _check_tree(tree):
    if not isinstance(tree, Tree):
        raise QueryError("tree must be a Tree")


def _check_root(tree, root):
    if not isinstance(root, int) or isinstance(root, bool):
        raise QueryError("root must be an int")
    if root < 0 or root >= tree.n:
        raise QueryError("root is out of range")


def _children(tree, node, parent):
    """node 去掉父节点之后的子节点列表。"""
    return [w for w in tree.neighbors(node) if w != parent]


def _rooted_iso_rec(ta, a, pa, tb, b, pb):
    """两棵已定根的子树是否同构：子节点两两配对，穷举所有配对方式。

    这是基线最贵的一步：每一层都要为子节点找到一个完美匹配，再递归下去。
    """
    ca = _children(ta, a, pa)
    cb = _children(tb, b, pb)
    if len(ca) != len(cb):
        return False
    if not ca:
        return True
    used = [False] * len(cb)

    def match(i):
        if i == len(ca):
            return True
        for j in range(len(cb)):
            if not used[j] and _rooted_iso_rec(ta, ca[i], a, tb, cb[j], b):
                used[j] = True
                if match(i + 1):
                    return True
                used[j] = False
        return False

    return match(0)


def rooted_isomorphic(tree_a, root_a, tree_b, root_b):
    """两棵有根树是否同构。根为顶点编号，必须落在各自树内。"""
    _check_tree(tree_a)
    _check_tree(tree_b)
    _check_root(tree_a, root_a)
    _check_root(tree_b, root_b)
    if tree_a.n != tree_b.n:
        return False
    return _rooted_iso_rec(tree_a, root_a, -1, tree_b, root_b, -1)


def unrooted_isomorphic(tree_a, tree_b):
    """两棵无根树是否同构。

    朴素做法：先求出每棵树的重心，再对每对重心做一次有根递归比较。
    """
    _check_tree(tree_a)
    _check_tree(tree_b)
    if tree_a.n != tree_b.n:
        return False
    if tree_a.n == 0:
        return True
    for ra in tree_a.centroids():
        for rb in tree_b.centroids():
            if _rooted_iso_rec(tree_a, ra, -1, tree_b, rb, -1):
                return True
    return False


def _cantor(a, b):
    """康托配对函数，对一对非负整数给出唯一非负整数。"""
    return (a + b) * (a + b + 1) // 2 + b


def _encode(seq):
    """把一个非负整数序列唯一地编码成一个非负整数，空序列编成零。"""
    acc = 0
    for value in reversed(seq):
        acc = _cantor(value, acc) + 1
    return acc


def rooted_canonical_hash(tree, root):
    """以 root 为根的有根树的规范哈希。

    递归地求每个子树的哈希，子节点哈希排序后唯一编码成当前顶点的哈希。
    两棵有根树同构当且仅当以对应根求得的规范哈希相等。
    """
    _check_tree(tree)
    _check_root(tree, root)

    def rec(node, parent):
        kids = [rec(w, node) for w in tree.neighbors(node) if w != parent]
        kids.sort()
        return _encode(kids)

    return rec(root, -1)


def canonical_hash(tree):
    """无根树的规范哈希。空树编成零。

    以全部重心为根分别求有根规范哈希，排序后再唯一编码；两棵无根树同构当且
    仅当规范哈希相等。
    """
    _check_tree(tree)
    if tree.n == 0:
        return _encode([])
    hashes = sorted(rooted_canonical_hash(tree, c) for c in tree.centroids())
    return _encode(hashes)


def group_isomorphic(trees):
    """把一组树按同构关系分组，返回下标分组。

    每个分组是若干下标组成的列表，分组之间按组内最小下标升序排列。朴素做法：
    每来一棵树就与已有的每个分组代表做一次两两递归比较。
    """
    if not isinstance(trees, (list, tuple)):
        raise QueryError("trees must be a list or tuple")
    for tree in trees:
        _check_tree(tree)
    groups = []
    for index, tree in enumerate(trees):
        placed = False
        for rep, members in groups:
            if unrooted_isomorphic(rep, tree):
                members.append(index)
                placed = True
                break
        if not placed:
            groups.append((tree, [index]))
    groups.sort(key=lambda item: item[1][0])
    return [members for _, members in groups]


def pairwise_comparison_count(trees):
    """朴素分组这一趟要做多少次两两递归比较。

    每来一棵树就与已有的每个分组代表比一次，落在同组就停手。
    """
    if not isinstance(trees, (list, tuple)):
        raise QueryError("trees must be a list or tuple")
    for tree in trees:
        _check_tree(tree)
    count = 0
    reps = []
    for tree in trees:
        for rep in reps:
            count += 1
            if unrooted_isomorphic(rep, tree):
                break
        else:
            reps.append(tree)
    return count


__all__ = [
    "TreehashError",
    "TreeError",
    "QueryError",
    "Tree",
    "rooted_isomorphic",
    "unrooted_isomorphic",
    "rooted_canonical_hash",
    "canonical_hash",
    "group_isomorphic",
    "pairwise_comparison_count",
]
