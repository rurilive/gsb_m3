"""treediam 现状：一棵简单树与一层朴素统计（改造前基线）。

树是有根的。节点用整数编号表示，根是构造时给定的编号。边可以带权重，可以为负。
邻接表由 add_edge 逐条累积而成，键是父节点，值是若干 (子节点, 权重) 二元组。
Tree 只提供最直白的工具：列节点、列全部点对、在两点之间走一遍求路径与路径权。

随后一层朴素统计，每个都用最直白、最好懂的方式算出来：能枚举就枚举，能反复
遍历就反复遍历。规模一小完全正确，规模一大就慢得离谱，但结果一定对。这里是
后续改造的对照基准。
"""


class Tree:
    """有根树：整数编号节点 + 带权邻接表（父到子累积）。

    root: 根节点编号。
    weights: 边权口径，取值 'edge' 或 'vertex'。
    """

    def __init__(self, root, weights="edge"):
        if weights not in ("edge", "vertex"):
            raise ValueError("weights must be 'edge' or 'vertex'")
        self._root = root
        self._weights = weights
        self._children = {root: []}

    @property
    def root(self):
        """根节点编号。"""
        return self._root

    @property
    def weights(self):
        """边权口径。"""
        return self._weights

    def add_edge(self, parent, child, weight=1):
        """给 parent 加一个孩子 child，边的权重为 weight；重复加边按追加处理。"""
        self._children.setdefault(parent, [])
        self._children.setdefault(child, [])
        self._children[parent].append((child, weight))

    def nodes(self):
        """全部节点编号，按编号从小到大排序。"""
        return sorted(self._children.keys())

    def children(self, node):
        """node 的孩子列表，按加入顺序。"""
        return list(self._children.get(node, []))

    def has_edge(self, parent, child):
        """parent 到 child 是否有一条边。"""
        for c, _ in self._children.get(parent, []):
            if c == child:
                return True
        return False

    def pairs(self):
        """全部点对 (a, b)，a 小于 b，按字典序。"""
        out = []
        ns = self.nodes()
        for i in range(len(ns)):
            for j in range(i + 1, len(ns)):
                out.append((ns[i], ns[j]))
        return out

    def parent_of(self, node):
        """在整张邻接表里找 node 的父节点；找不到（node 是根）返回 None。"""
        for p, kids in self._children.items():
            for c, _ in kids:
                if c == node:
                    return p
        return None

    def edge_weight(self, a, b):
        """取相邻两点 a 与 b 之间那条边的权重，两个方向都认。"""
        for c, w in self._children.get(a, []):
            if c == b:
                return w
        for c, w in self._children.get(b, []):
            if c == a:
                return w
        raise KeyError((a, b))

    def adjacent(self, node):
        """node 的全部邻居，值为 (邻居, 边权)，父与孩子都算，按发现顺序。"""
        out = []
        p = self.parent_of(node)
        if p is not None:
            out.append((p, self.edge_weight(p, node)))
        for c, w in self._children.get(node, []):
            out.append((c, w))
        return out

    def path(self, a, b):
        """朴素求 a 到 b 的路径：自 a 起对整张邻接图深度优先，第一次碰到 b 就返回。

        返回值是路径上的节点编号列表，含两端。两点不连通时返回 None。
        """
        stack = [(a, [a])]
        seen = {a}
        while stack:
            node, acc = stack.pop()
            if node == b:
                return acc
            for nxt, _ in self.adjacent(node):
                if nxt in seen:
                    continue
                seen.add(nxt)
                stack.append((nxt, acc + [nxt]))
        return None

    def path_weight(self, a, b):
        """朴素求 a 到 b 的路径权值和。

        edge 口径下是路径上各边权之和；vertex 口径下是路径上各节点权重之和，
        节点权重按编号取值（编号即权重），两端都计入。两点不连通抛 KeyError。
        """
        p = self.path(a, b)
        if p is None:
            raise KeyError((a, b))
        if self._weights == "vertex":
            return sum(node for node in p)
        total = 0
        for i in range(len(p) - 1):
            total += self.edge_weight(p[i], p[i + 1])
        return total

    def traverse(self, start):
        """从 start 出发走遍全树，按访问顺序返回节点编号列表。

        朴素做法：先自 start 沿父边一路爬到根，记下爬升路径，再自根对整棵树
        做一次深度优先遍历，最后把爬升路径接在遍历序列之后。访问序列因此
        随起点不同而不同，但一个起点对应一个确定序列。
        """
        chain = [start]
        seen = {start}
        cur = start
        while True:
            p = self.parent_of(cur)
            if p is None or p in seen:
                break
            seen.add(p)
            chain.append(p)
            cur = p

        order = []
        stack = [self._root]
        visited = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            kids = [c for c, _ in self._children.get(node, [])]
            for c in reversed(kids):
                if c not in visited:
                    stack.append(c)
        for node in chain[1:]:
            order.append(node)
        return order


class DiameterError(Exception):
    """treediam 的错误基类。当前只有森林不成树一种情形。"""


class ForestError(DiameterError):
    """输入不是一棵树（要么成林，要么带环）。"""


def in_same_root(tree, a, b):
    """朴素判断两点是否连通：从 a 出发走遍可达点，看 b 在不在里面。"""
    stack = [a]
    seen = {a}
    while stack:
        node = stack.pop()
        for nxt, _ in tree.adjacent(node):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return b in seen


def reachable_from(tree, start):
    """从 start 出发可达的全部节点，按编号排序。"""
    stack = [start]
    seen = {start}
    while stack:
        node = stack.pop()
        for nxt, _ in tree.adjacent(node):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return sorted(seen)


def is_tree(tree):
    """朴素判断是不是一棵树：全连通且不存在环。

    先看边数与节点数的关系，再从根走一遍看能否遍历到所有点。
    """
    ns = tree.nodes()
    if not ns:
        return False
    edge_count = 0
    for node in ns:
        edge_count += len(tree.children(node))
    if edge_count != len(ns) - 1:
        return False
    reached = reachable_from(tree, tree.root)
    return len(reached) == len(ns)


def farthest_from(tree, start):
    """朴素求离 start 最远的点：把每个节点跟 start 的距离都算一遍取最大。

    距离定义跟着边权口径走。返回 (最远点, 最大距离)；并列时取编号小的。
    多处并列先到先得，比较时严格大于才替换，节点按编号升序扫描。
    """
    best_node = None
    best_dist = None
    for node in tree.nodes():
        d = tree.path_weight(start, node)
        if best_dist is None or d > best_dist:
            best_dist = d
            best_node = node
    return best_node, best_dist


def all_distances(tree, start):
    """朴素求 start 到每个点的距离，返回 {节点: 距离}。"""
    out = {}
    for node in tree.nodes():
        out[node] = tree.path_weight(start, node)
    return out


def diameter(tree):
    """朴素求直径：枚举所有点对，逐个算路径权取最大。

    返回 (直径长度, 端点甲, 端点乙)。端点按编号升序给出；并列时取字典序
    最小的那一对。不是树就抛 ForestError。
    """
    if not is_tree(tree):
        raise ForestError("input is not a single tree")
    best_len = None
    best_pair = None
    for a, b in tree.pairs():
        w = tree.path_weight(a, b)
        if best_len is None or w > best_len:
            best_len = w
            best_pair = (a, b)
    if best_pair is None:
        ns = tree.nodes()
        return 0, ns[0], ns[0]
    return best_len, best_pair[0], best_pair[1]


def diameter_path(tree):
    """朴素求直径路径：拿到直径两点后再单独求一次路径。"""
    _, a, b = diameter(tree)
    return tree.path(a, b)


def farthest_distance(tree, start):
    """朴素求 start 到最远点的距离。"""
    return farthest_from(tree, start)[1]


def eccentricity_max(tree):
    """朴素求每个点到最远点的距离里最大的那个。

    返回 (最大偏心距所在点, 该点偏心距)；并列时取编号小的。
    """
    best_node = None
    best_val = None
    for node in tree.nodes():
        v = farthest_distance(tree, node)
        if best_val is None or v > best_val:
            best_val = v
            best_node = node
    return best_node, best_val


def distance_sum(tree, start):
    """朴素求 start 到所有点的距离之和。"""
    total = 0
    for node in tree.nodes():
        total += tree.path_weight(start, node)
    return total


def all_distance_sums(tree):
    """朴素求每个点到所有点的距离之和，返回 {节点: 距离和}。"""
    out = {}
    for node in tree.nodes():
        out[node] = distance_sum(tree, node)
    return out


def max_distance_sum_point(tree):
    """朴素求距离和最大的点，返回 (点, 距离和)；并列时取编号小的。"""
    sums = all_distance_sums(tree)
    best_node = None
    best_val = None
    for node in tree.nodes():
        v = sums[node]
        if best_val is None or v > best_val:
            best_val = v
            best_node = node
    return best_node, best_val


def pair_distance_sum(tree):
    """朴素求所有点对距离之和：枚举每一对，逐个算路径权再累加。"""
    total = 0
    for a, b in tree.pairs():
        total += tree.path_weight(a, b)
    return total


def components(tree):
    """朴素把图切成若干连通分量，返回分量列表，每个分量是升序节点列表。"""
    left = set(tree.nodes())
    out = []
    while left:
        start = min(left)
        comp = reachable_from(tree, start)
        out.append(comp)
        left -= set(comp)
    return out


def center(tree):
    """朴素求树的中心：枚举每个点，算它到最远点的距离，取最小者。

    返回 (中心点, 该点到最远点的距离)；并列时取编号小的。
    """
    best_node = None
    best_val = None
    for node in tree.nodes():
        v = farthest_distance(tree, node)
        if best_val is None or v < best_val:
            best_val = v
            best_node = node
    return best_node, best_val


def centroid(tree):
    """朴素求树的重心：去掉某点后最大连通块最小的那种点。

    枚举每个候选点，把它从图里摘掉，再跑一遍连通分量，取最大分量的点数；
    使这个最大分量最小的点即重心。并列时取编号小的。返回节点编号。
    """
    ns = tree.nodes()
    best_node = None
    best_size = None
    for cand in ns:
        largest = _largest_piece_without(tree, cand)
        if best_size is None or largest < best_size:
            best_size = largest
            best_node = cand
    return best_node


def _largest_piece_without(tree, removed):
    """把 removed 摘掉后，最大连通块的节点数（不含 removed 自己）。

    摘点后遍历要绕开 removed，不能借它当中转，否则会把本应分开的两块并成一块。
    """
    left = set(tree.nodes())
    left.discard(removed)
    largest = 0
    while left:
        start = min(left)
        comp = _reach_without(tree, start, removed)
        largest = max(largest, len(comp))
        left -= set(comp)
    return largest


def _reach_without(tree, start, removed):
    """从 start 出发可达的点，绕开 removed，返回升序列表。"""
    stack = [start]
    seen = {start}
    while stack:
        node = stack.pop()
        for nxt, _ in tree.adjacent(node):
            if nxt == removed:
                continue
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return sorted(seen)
