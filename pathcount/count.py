"""pathcount.count：有向图定长路径计数的朴素实现（改造前基线）。

围绕一张有向简单图做路径计数，眼下全是最直白的一条路：

  - count_walks_exact  恰好走 steps 步的走法数：从起点起逐层深度搜索，
                       把每一条长度为 steps 的走法整条枚举出来再数个数；
  - count_paths_between 两点之间全部路径的条数：同样靠深度搜索枚举路径，
                       走过的点不再重复（简单路径），枚举完计数；
  - count_walks_up_to   长度不超过 bound 的走法数：对每个长度分别枚举再累加；
  - has_cycle_of_length 长度恰为 length 的回路是否存在，以及 shortest_cycle
                       最长回路长度：按长度从小到大枚举，取第一个命中的；
  - mat_mul             矩阵乘法：三重循环逐项累加；
  - mat_pow             矩阵幂：把同一个矩阵逐次相乘 exponent 遍。

这些做法直观可靠，结果一眼能看穿，可步数或点数一多就是指数乃至立方量级
地退下去。本文件是改造前的基线，朴素路径在改造之后不得删除，新的快速路径
必须与它对同一批输入给出的结果逐项对齐。

异常统一继承 PathErro 基类：GraphErro / WalkerErro。
"""


class PathErro(Exception):
    """路径计数库所有异常的基类，非法输入与非法操作一律快速失败。"""


class GraphErro(PathErro):
    """图的构造非法：节点重复、端点类型不对、端点不在图中、边不是二元素。"""


class WalkerErro(PathErro):
    """查询非法：步数为负、两点不在图里、上界为负、长度为负。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 WalkerErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise WalkerErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _norm_nodes(nodes):
    """节点序列规整成整数元组：缺省用零到n减一，重复即抛 GraphErro。"""
    if nodes is None:
        raise GraphErro("节点列表：必须显式给出，不能为空")
    try:
        items = list(nodes)
    except TypeError:
        raise GraphErro("节点列表：必须是可迭代对象，收到 %r" % (nodes,))
    out = []
    seen = set()
    for item in items:
        if isinstance(item, bool) or not isinstance(item, int):
            raise GraphErro("节点列表：节点必须是整数，收到 %r" % (item,))
        if item in seen:
            raise GraphErro("节点列表：节点重复出现 %r" % (item,))
        seen.add(item)
        out.append(item)
    return tuple(out)


def _check_node(node, members, where):
    """边端点必须已经是节点列表里登记过的整数节点。"""
    if isinstance(node, bool) or not isinstance(node, int):
        raise GraphErro("%s：端点必须是整数，收到 %r" % (where, node))
    if node not in members:
        raise GraphErro("%s：端点 %r 不在节点列表里" % (where, node))
    return node


def mat_mul(a, b, mod):
    """朴素矩阵乘法：三重循环，内层逐项累加，最后统一对模取余。

    形状不匹配（左侧列数不等于右侧行数）抛 WalkerErro；行长度参差不齐抛
    WalkerErro；乘积超出 64 位时纯 Python 整数不会溢出。mod 不是正数抛
    WalkerErro。空矩阵按平凡结果处理。
    """
    mod = _as_int(mod, "矩阵乘法取模")
    if mod <= 0:
        raise WalkerErro("矩阵乘法：模必须是正整数，收到 %r" % (mod,))
    na = len(a)
    ca = len(a[0]) if na else 0
    for i in range(1, na):
        if len(a[i]) != ca:
            raise WalkerErro("矩阵乘法：左侧第 %d 行长度与首行不一致" % (i + 1))
    nb = len(b)
    cb = len(b[0]) if nb else 0
    for j in range(1, nb):
        if len(b[j]) != cb:
            raise WalkerErro("矩阵乘法：右侧第 %d 行长度与首行不一致" % (j + 1))
    if ca != nb:
        raise WalkerErro("矩阵乘法：左矩阵列数 %d 与右矩阵行数 %d 不匹配"
                         % (ca, nb))
    if na == 0 or cb == 0:
        return []
    out = [[0] * cb for _ in range(na)]
    for i in range(na):
        for j in range(cb):
            acc = 0
            for t in range(ca):
                acc += a[i][t] * b[t][j]
            out[i][j] = acc % mod
    return out


def mat_pow(a, e, mod):
    """朴素矩阵幂：把同一个矩阵逐次相乘，指数多大就乘多少次。

    指数为负抛 WalkerErro；指数为零返回同阶单位矩阵；非方阵抛 WalkerErro。
    指数很大时这里要做指数那么多次矩阵乘法，每次乘法又是立方量级。
    """
    e = _as_int(e, "矩阵幂指数")
    if e < 0:
        raise WalkerErro("矩阵幂：指数不能为负，收到 %r" % (e,))
    n = len(a)
    if n == 0:
        return []
    for i in range(n):
        if len(a[i]) != n:
            raise WalkerErro("矩阵幂：只支持方阵，第 %d 行长度不是 %d"
                             % (i + 1, n))
    out = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    for _ in range(e):
        out = mat_mul(out, a, mod)
    return out


class DirectedGraph:
    """有向图，节点用整数编号，允许重边，允许自环。

    自环即两端为同一节点的边，自环是一条长度为 1 的回路，在计数与回路判定
    里都按普通边参与。构造之后邻接表与邻接矩阵一次建成，不再变动。入参是
    节点列表与有向边列表，边列表里同一条边出现两次就是两条平行边。
    """

    def __init__(self, nodes=None, edges=None):
        self._nodes = _norm_nodes(nodes)
        self._index = {node: i for i, node in enumerate(self._nodes)}
        n = len(self._nodes)
        self._matrix = [[0] * n for _ in range(n)]
        if edges is None:
            edges = []
        try:
            edge_items = list(edges)
        except TypeError:
            raise GraphErro("边列表：必须是可迭代对象，收到 %r" % (edges,))
        for edge in edge_items:
            try:
                u, v = edge
            except (TypeError, ValueError):
                raise GraphErro("边列表：每条边必须是二元素，收到 %r" % (edge,))
            iu = _check_node(u, self._index, "边列表")
            iv = _check_node(v, self._index, "边列表")
            self._matrix[iu][iv] += 1

    def nodes(self):
        """按登记顺序返回全部节点。"""
        return list(self._nodes)

    def has_node(self, node):
        """节点是否已登记。"""
        return node in self._index

    def edges(self):
        """按 u、v 升序返回全部有向边，多重边逐条列出。"""
        out = []
        n = len(self._nodes)
        for i in range(n):
            for j in range(n):
                for _ in range(self._matrix[i][j]):
                    out.append((self._nodes[i], self._nodes[j]))
        return out

    def has_edge(self, u, v):
        """u 到 v 是否有至少一条有向边。"""
        iu = self._index_of(u)
        iv = self._index_of(v)
        return self._matrix[iu][iv] > 0

    def edge_count(self, u, v):
        """u 到 v 的有向边条数，最小为零，允许重边。"""
        iu = self._index_of(u)
        iv = self._index_of(v)
        return self._matrix[iu][iv]

    def adjacency_matrix(self):
        """返回邻接矩阵的逐元素副本，行列为节点的登记顺序。"""
        return [row[:] for row in self._matrix]

    def out_neighbors(self, u):
        """u 的直接后继，按节点编号升序，多重边只出现一次。"""
        iu = self._index_of(u)
        n = len(self._nodes)
        return [self._nodes[j] for j in range(n) if self._matrix[iu][j] > 0]

    def _index_of(self, node):
        if isinstance(node, bool) or not isinstance(node, int):
            raise WalkerErro("节点：必须是整数，收到 %r" % (node,))
        if node not in self._index:
            raise WalkerErro("节点：%r 不在图里" % (node,))
        return self._index[node]


class PathCounter:
    """有向图定长路径计数的朴素工具集（改造前基线）。

    每条查询开始前把内部计数归零后重新累加：depth_steps 记深度搜索访问
    过的节点次数，enum_paths 记枚举出来的路径条数，mult_count 记矩阵乘法
    的次数。
    """

    def __init__(self, graph):
        if not isinstance(graph, DirectedGraph):
            raise WalkerErro("路径计数：需要一张有向图，收到 %r" % (graph,))
        self._graph = graph
        self.depth_steps = 0
        self.enum_paths = 0
        self.mult_count = 0

    # ----------------------------------------------------------------
    # 恰好走 steps 步的走法数：逐层深度搜索枚举全部走法
    # ----------------------------------------------------------------
    def count_walks_exact(self, start, end, steps):
        """数出从 start 到 end 恰好走 steps 步的走法条数。

        走法允许重复经过节点与边，靠逐层深度搜索把每一条长度为 steps 的
        走法整条枚举出来再计数。steps 为零时只看两端是否相同（边界：空走
        法）。steps 为负抛 WalkerErro；两端不在图里抛 WalkerErro。
        """
        steps = _as_int(steps, "走法步数")
        if steps < 0:
            raise WalkerErro("走法步数：不能为负，收到 %r" % (steps,))
        self.depth_steps = 0
        self.enum_paths = 0
        self._index_of(start)
        self._index_of(end)
        if steps == 0:
            self.enum_paths += 1
            return 1 if start == end else 0
        total = 0
        stack = [(start, 0)]
        while stack:
            node, depth = stack.pop()
            self.depth_steps += 1
            if depth == steps:
                self.enum_paths += 1
                if node == end:
                    total += 1
                continue
            for nxt in self._neighbors(node):
                stack.append((nxt, depth + 1))
        return total

    # ----------------------------------------------------------------
    # 两点之间全部路径的条数：深度搜索枚举简单路径
    # ----------------------------------------------------------------
    def count_paths_between(self, start, end):
        """数出从 start 到 end 的全部简单路径条数（不重复经过节点）。

        同样靠深度搜索枚举路径，走过的节点进访问集不再回头，枚举完计数。
        起点与终点相同按单节点路径记一条。两端不在图里抛 WalkerErro。
        """
        self.depth_steps = 0
        self.enum_paths = 0
        self._index_of(start)
        self._index_of(end)
        if start == end:
            self.enum_paths += 1
            return 1
        total = 0
        visited = {start}
        stack = [(start, iter(self._neighbors(start)))]
        while stack:
            node, it = stack[-1]
            self.depth_steps += 1
            advanced = False
            for nxt in it:
                if nxt in visited:
                    continue
                advanced = True
                if nxt == end:
                    self.enum_paths += 1
                    total += 1
                    continue
                visited.add(nxt)
                stack.append((nxt, iter(self._neighbors(nxt))))
                break
            if not advanced:
                stack.pop()
                visited.discard(node)
        return total

    # ----------------------------------------------------------------
    # 长度不超过 bound 的走法数：对每个长度分别枚举再累加
    # ----------------------------------------------------------------
    def count_walks_up_to(self, start, end, bound):
        """数出从 start 到 end 长度不超过 bound 的全部走法条数。

        长度从零一路数到 bound，每个长度都各自深度搜索枚举一遍，再把各长度
        的结果累加起来。bound 为负抛 WalkerErro；两端不在图里抛 WalkerErro。
        """
        bound = _as_int(bound, "上界")
        if bound < 0:
            raise WalkerErro("上界：不能为负，收到 %r" % (bound,))
        self.depth_steps = 0
        self.enum_paths = 0
        total = 0
        for length in range(bound + 1):
            total += self._enumerate_exact(start, end, length)
        return total

    # ----------------------------------------------------------------
    # 回路：按长度从小到大枚举，判定存在与最短
    # ----------------------------------------------------------------
    def has_cycle_of_length(self, length):
        """是否存在长度恰为 length 的回路。

        回路是起点与终点相同的走法，长度至少为一；对每个节点分别从长度一
        枚举到 length，命中即返回 True。length 为零或为负抛 WalkerErro。
        """
        length = _as_int(length, "回路长度")
        if length <= 0:
            raise WalkerErro("回路长度：必须是正整数，收到 %r" % (length,))
        self.depth_steps = 0
        self.enum_paths = 0
        for node in self._graph.nodes():
            if self._enumerate_exact(node, node, length) > 0:
                return True
        return False

    def shortest_cycle(self):
        """返回最短回路的长度，没有回路时返回 None。

        按回路长度从小到大逐个尝试，长度从一起到节点数为止（简单回路长度
        不超过节点数），第一个命中的长度就是最短回路长度。
        """
        self.depth_steps = 0
        self.enum_paths = 0
        n = len(self._graph.nodes())
        for length in range(1, n + 1):
            for node in self._graph.nodes():
                if self._enumerate_exact(node, node, length) > 0:
                    return length
        return None

    # ----------------------------------------------------------------
    # 矩阵幂：朴素逐次相乘，与快速幂路对照
    # ----------------------------------------------------------------
    def mat_pow(self, a, e, mod):
        """朴素矩阵幂，外层按指数逐次相乘，内部走三重循环的 mat_mul。

        每次乘法计一次 mult_count。指数为负、非方阵、模不是正数抛
        WalkerErro。与快速幂路对同一批输入必须给出相同矩阵。
        """
        e = _as_int(e, "矩阵幂指数")
        if e < 0:
            raise WalkerErro("矩阵幂：指数不能为负，收到 %r" % (e,))
        n = len(a)
        if n == 0:
            return []
        for i in range(n):
            if len(a[i]) != n:
                raise WalkerErro("矩阵幂：只支持方阵，第 %d 行长度不是 %d"
                                 % (i + 1, n))
        self.mult_count = 0
        out = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
        for _ in range(e):
            self.mult_count += 1
            out = mat_mul(out, a, mod)
        return out

    # ----------------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------------
    def _index_of(self, node):
        return self._graph._index_of(node)

    def _neighbors(self, node):
        return self._graph.out_neighbors(node)

    def _enumerate_exact(self, start, end, steps):
        """从 start 起深度搜索，数恰好走 steps 步落到 end 的走法条数。

        这个内部枚举器把访问过的节点次数记进 depth_steps，把数到的走法记
        进 enum_paths，供上层各种查询复用。
        """
        if steps == 0:
            self.enum_paths += 1
            return 1 if start == end else 0
        total = 0
        stack = [(start, 0)]
        while stack:
            node, depth = stack.pop()
            self.depth_steps += 1
            if depth == steps:
                self.enum_paths += 1
                if node == end:
                    total += 1
                continue
            for nxt in self._neighbors(node):
                stack.append((nxt, depth + 1))
        return total
