"""异常层次、建树工具与基线朴素查询：沿父指针逐级走，或整棵子树枚举。"""


class QueryError(Exception):
    """本包所有异常的基类。"""


class InvalidNodeError(QueryError):
    """端点下标越界或不属于本树。"""


class InvalidArgumentError(QueryError):
    """构造或调用参数非法。"""


def build_tree(node_count, parents, weights):
    """把父指针数组与点权数组规整成字典。

    parents[0] 置 -1 表示根；parents[i] 是 i 的父亲。返回
    {"n", "parent", "weight", "children"}，children 按升序排列以保证确定性。
    """
    if node_count < 1:
        raise InvalidNodeError("节点数必须为正")
    if len(parents) != node_count or len(weights) != node_count:
        raise InvalidNodeError("父指针或点权长度与节点数不符")
    parent = [-1] * node_count
    weight = [0] * node_count
    children = [[] for _ in range(node_count)]
    for i in range(node_count):
        p = parents[i]
        if i == 0:
            if p not in (-1, 0):
                raise InvalidNodeError("根节点的父指针必须是 -1")
            parent[i] = -1
        else:
            if p < 0 or p >= node_count:
                raise InvalidNodeError("父指针越界：%r" % (p,))
            parent[i] = p
        weight[i] = int(weights[i])
    for i in range(1, node_count):
        children[parent[i]].append(i)
    for c in children:
        c.sort()
    return {"n": node_count, "parent": parent, "weight": weight, "children": children}


def node_path(tree, u, v):
    """朴素地沿父指针回升，返回 u 到 v 的节点序列（含两端）。"""
    n = tree["n"]
    for x in (u, v):
        if not (0 <= x < n):
            raise InvalidNodeError("端点越界：%r" % (x,))
    parent = tree["parent"]
    up_u = [u]
    pos = {u: 0}
    cur = u
    while cur != 0:
        cur = parent[cur]
        pos[cur] = len(up_u)
        up_u.append(cur)
    chain = [v]
    cur = v
    while cur not in pos:
        cur = parent[cur]
        chain.append(cur)
    meet = cur
    lca_index = pos[meet]
    nodes = up_u[: lca_index + 1] + chain[::-1][1:]
    return nodes


def chain_end_naive(tree, u):
    """朴素地自 u 向根走：只要 u 是父的唯一儿子就继续上行，返回停下的节点。

    这一步每次要看一遍父亲的全部孩子，是基线里最直白的写法。
    """
    parent = tree["parent"]
    children = tree["children"]
    if not (0 <= u < tree["n"]):
        raise InvalidNodeError("端点越界：%r" % (u,))
    cur = u
    while cur != 0:
        p = parent[cur]
        if len(children[p]) != 1:
            break
        cur = p
    return cur


def _depths(tree):
    parent = tree["parent"]
    n = tree["n"]
    depth = [0] * n
    for i in range(n):
        d = 0
        cur = i
        while cur != 0:
            cur = parent[cur]
            d += 1
        depth[i] = d
    return depth


class PathQuerier:
    """朴素树上查询器，所有口径都直白枚举，规模一大就慢。"""

    def __init__(self, node_count, parents, weights):
        self.tree = build_tree(node_count, parents, weights)
        self.weight = list(self.tree["weight"])
        self.steps = 0

    # -- 内部工具 --------------------------------------------------------
    def _check(self, x):
        if not (0 <= x < self.tree["n"]):
            raise InvalidNodeError("端点越界：%r" % (x,))

    def _path(self, u, v):
        self._check(u)
        self._check(v)
        nodes = node_path(self.tree, u, v)
        self.steps += len(nodes)
        return nodes

    def _subtree(self, u):
        self._check(u)
        stack = [u]
        order = []
        while stack:
            x = stack.pop()
            order.append(x)
            self.steps += 1
            for c in self.tree["children"][x]:
                stack.append(c)
        return order

    # -- 能力一：路径权值和 ---------------------------------------------
    def path_sum(self, u, v):
        nodes = self._path(u, v)
        return sum(self.weight[x] for x in nodes)

    # -- 能力二：路径最大值 ---------------------------------------------
    def path_max(self, u, v):
        nodes = self._path(u, v)
        return max(self.weight[x] for x in nodes)

    # -- 能力三：子树权值和 ---------------------------------------------
    def subtree_sum(self, u):
        nodes = self._subtree(u)
        return sum(self.weight[x] for x in nodes)

    # -- 单点修改 --------------------------------------------------------
    def update(self, u, value):
        self._check(u)
        self.steps += 1
        self.weight[u] = int(value)
        return self.weight[u]

    # -- 派生：路径和最大与端点 -----------------------------------------
    def best_path(self):
        """在所有无序点对里找路径权值和最大的一对，返回 (和, 端点甲, 端点乙)。

        和相同则取端点下标字典序最小的一对，保证确定性。
        """
        n = self.tree["n"]
        best_sum = None
        best_pair = None
        for i in range(n):
            for j in range(i, n):
                nodes = node_path(self.tree, i, j)
                self.steps += len(nodes)
                s = sum(self.weight[x] for x in nodes)
                if best_sum is None or s > best_sum or (s == best_sum and (i, j) < best_pair):
                    best_sum = s
                    best_pair = (i, j)
        return best_sum, best_pair[0], best_pair[1]

    # -- 派生：逐级步数 -------------------------------------------------
    def walk_steps(self, u, v):
        """显式统计从 u 与 v 两端逐级走到汇合点的步数，用于规模对照。"""
        self._check(u)
        self._check(v)
        parent = self.tree["parent"]
        depth = _depths(self.tree)
        total = 0
        a, b = u, v
        while a != b:
            if depth[a] >= depth[b]:
                a = parent[a]
            else:
                b = parent[b]
            total += 1
            self.steps += 1
        return total


def step_count(querier, u, v):
    """便捷函数：返回一次路径查询累计的逐步步数。"""
    before = querier.steps
    querier.path_sum(u, v)
    return querier.steps - before
