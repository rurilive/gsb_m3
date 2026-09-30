"""改造前的朴素实现：DsuTree 逐结点重走子树统计颜色。

树的根固定为编号 0，边以无向对给出，颜色编号为非负整数。

朴素口径：对每个结点 ``u``，从 ``u`` 出发深搜以 ``u`` 为根的整棵子树，
途中用字典累加每种颜色出现的次数，再在字典里挑出频次最高的颜色
（并列时取颜色编号最小者）。每个结点都把这棵子树重新走一遍，
结点一多、树一深，代价随子树规模反复累加，退到平方甚至更高量级。
"""

__all__ = [
    "DsuTree",
    "DsuError",
    "DsuInputError",
    "UnknownNodeError",
    "DisconnectedError",
]


class DsuError(Exception):
    """本模块所有异常的基类。"""


class DsuInputError(DsuError):
    """结点数、边或颜色取值不合法。"""


class UnknownNodeError(DsuError):
    """查询引用了不在树中的结点编号。"""


class DisconnectedError(DsuError):
    """给出的边没有连成一棵覆盖全部结点的树。"""


class DsuTree:
    """载入一棵带颜色的有根树，给出每棵子树内的颜色频次与主色。

    邻接表、颜色表与父子关系都保存在实例上，模块级不持有任何可变状态，
    同一实例对固定输入重复查询结果一致。
    """

    def __init__(self):
        self._n = 0
        self._color = []
        self._adj = []
        self._children = []
        self._loaded = False

    # ------------------------------------------------------------------
    # 载入与校验
    # ------------------------------------------------------------------
    def load(self, n, edges, colors):
        """载入结点数为 n 的树，根为 0。

        edges 是 (u, v) 无序点对列表，共 n 减 1 条；
        colors 是长度 n 的颜色编号列表，编号为非负整数。
        """
        if not isinstance(n, int) or n <= 0:
            raise DsuInputError("结点数必须为正整数: %r" % (n,))
        if len(colors) != n:
            raise DsuInputError("颜色个数与结点数不符: %d 与 %d" % (len(colors), n))
        for c in colors:
            if not isinstance(c, int) or c < 0:
                raise DsuInputError("颜色编号必须为非负整数: %r" % (c,))
        for e in edges:
            if len(e) != 2:
                raise DsuInputError("边必须是两点对: %r" % (e,))
            for x in e:
                if not isinstance(x, int) or x < 0 or x >= n:
                    raise DsuInputError("边端点越界: %r" % (x,))
        if len(edges) != n - 1:
            raise DisconnectedError("树的边数应为结点数减一: %d" % (len(edges),))
        adj = [[] for _ in range(n)]
        for u, v in edges:
            adj[u].append(v)
            adj[v].append(u)
        # 与查询无关的稳定顺序: 邻接表按编号升序，保证遍历次序确定
        for row in adj:
            row.sort()
        # 以 0 为根做一次遍历，得到父子关系与可达性
        parent = [-1] * n
        seen = [False] * n
        seen[0] = True
        stack = [0]
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if not seen[w]:
                    seen[w] = True
                    parent[w] = u
                    stack.append(w)
        if not all(seen):
            raise DisconnectedError("给出的边没有连成一棵覆盖全部结点的树")
        children = [[] for _ in range(n)]
        for u in range(n):
            if parent[u] != -1:
                children[parent[u]].append(u)
        for row in children:
            row.sort()
        self._n = n
        self._color = list(colors)
        self._adj = adj
        self._children = children
        self._loaded = True

    def _check_loaded(self):
        if not self._loaded:
            raise DsuInputError("尚未载入任何树")

    # ------------------------------------------------------------------
    # 朴素统计: 每个结点单独深搜整棵子树
    # ------------------------------------------------------------------
    def _collect(self, u, bucket):
        """从 u 出发深搜整棵子树，把颜色计数累加进 bucket。"""
        stack = [u]
        while stack:
            x = stack.pop()
            c = self._color[x]
            bucket[c] = bucket.get(c, 0) + 1
            for w in self._children[x]:
                stack.append(w)

    def _dominant(self, counts):
        """从颜色计数里挑频次最高的颜色，并列取编号最小者。"""
        if not counts:
            return None
        best_color = None
        best_count = -1
        for c in sorted(counts.keys()):
            if counts[c] > best_count:
                best_count = counts[c]
                best_color = c
        return best_color

    def subtree_counts(self, u):
        """返回以 u 为根的子树内颜色到出现次数的映射（副本）。"""
        self._check_loaded()
        self._check_node(u)
        bucket = {}
        self._collect(u, bucket)
        return dict(bucket)

    def dominant_color(self, u):
        """返回以 u 为根的子树内的主色编号，并列取最小者。"""
        self._check_loaded()
        self._check_node(u)
        bucket = {}
        self._collect(u, bucket)
        return self._dominant(bucket)

    # ------------------------------------------------------------------
    # 全量口径
    # ------------------------------------------------------------------
    def all_dominant_colors(self):
        """返回结点编号到主色编号的映射，逐结点单独统计。"""
        self._check_loaded()
        result = {}
        for u in range(self._n):
            bucket = {}
            self._collect(u, bucket)
            result[u] = self._dominant(bucket)
        return result

    def all_subtree_counts(self):
        """返回结点编号到颜色频次映射的映射，逐结点单独统计。"""
        self._check_loaded()
        result = {}
        for u in range(self._n):
            bucket = {}
            self._collect(u, bucket)
            result[u] = dict(bucket)
        return result

    def node_count(self):
        """返回结点个数。"""
        self._check_loaded()
        return self._n

    def visit_count(self):
        """返回逐结点单独统计时访问结点的总次数。

        朴素口径下，结点 u 的统计要把它整棵子树走一遍，故总次数是
        全部子树规模之和。
        """
        self._check_loaded()
        total = 0
        for u in range(self._n):
            size = 0
            stack = [u]
            while stack:
                x = stack.pop()
                size += 1
                for w in self._children[x]:
                    stack.append(w)
            total += size
        return total

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _check_node(self, u):
        if not isinstance(u, int) or u < 0 or u >= self._n:
            raise UnknownNodeError("未知结点编号: %r" % (u,))
