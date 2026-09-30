"""改造前的朴素实现：LongChainTree 逐结点重走子树统计深度。

树的根固定为编号 0，边以无向对给出，结点权重为非负整数。

朴素口径分两处：

其一，划分重儿子时只看子树节点数，子树节点数最大的儿子记作重儿子，
并列时取编号最小者。这与按子树深度最大值划分的口径不同。

其二，计算某结点子树内每个深度的节点分布时，对每棵子树先深搜一遍
求出它相对子树的深度分布，再把各儿子的深度数组整份取出、逐个元素
拷贝进一张新数组相加。每个结点都要新建一份长度等于其深度的完整数组，
深度一深、结点一多，拷贝总量迅速膨胀，退到平方甚至更高量级。
"""

__all__ = [
    "LongChainTree",
    "Erro",
    "InputErro",
    "UnknownNodeErro",
    "DisconnectedErro",
]


class Erro(Exception):
    """本模块所有异常的基类。"""


class InputErro(Erro):
    """结点数、边或权重取值不合法。"""


class UnknownNodeErro(Erro):
    """查询引用了不在树中的结点编号。"""


class DisconnectedErro(Erro):
    """给出的边没有连成一棵覆盖全部结点的树。"""


class LongChainTree:
    """载入一棵带权有根树，给出若干按子树深度统计的答案。

    邻接表、权重表与父子关系都保存在实例上，模块级不持有任何可变状态，
    同一实例对固定输入重复查询结果一致。
    """

    def __init__(self):
        self._n = 0
        self._weight = []
        self._adj = []
        self._children = []
        self._size = []
        self._loaded = False

    # ------------------------------------------------------------------
    # 载入与校验
    # ------------------------------------------------------------------
    def load(self, n, edges, weights):
        """载入结点数为 n 的树，根为 0。

        edges 是 (u, v) 无序点对列表，共 n 减 1 条；
        weights 是长度 n 的结点权重列表，权重为非负整数。
        """
        if not isinstance(n, int) or n <= 0:
            raise InputErro("结点数必须为正整数: %r" % (n,))
        if len(weights) != n:
            raise InputErro("权重个数与结点数不符: %d 与 %d" % (len(weights), n))
        for w in weights:
            if not isinstance(w, int) or w < 0:
                raise InputErro("权重必须为非负整数: %r" % (w,))
        for e in edges:
            if len(e) != 2:
                raise InputErro("边必须是两点对: %r" % (e,))
            for x in e:
                if not isinstance(x, int) or x < 0 or x >= n:
                    raise InputErro("边端点越界: %r" % (x,))
        if len(edges) != n - 1:
            raise DisconnectedErro("树的边数应为结点数减一: %d" % (len(edges),))
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
            raise DisconnectedErro("给出的边没有连成一棵覆盖全部结点的树")
        children = [[] for _ in range(n)]
        for u in range(n):
            if parent[u] != -1:
                children[parent[u]].append(u)
        for row in children:
            row.sort()
        self._n = n
        self._weight = list(weights)
        self._adj = adj
        self._children = children
        # 子树节点数
        size = [1] * n
        for u in range(n - 1, -1, -1):
            for w in self._children[u]:
                size[u] += size[w]
        self._size = size
        self._loaded = True

    def _check_loaded(self):
        if not self._loaded:
            raise InputErro("尚未载入任何树")

    def _check_node(self, u):
        if not isinstance(u, int) or u < 0 or u >= self._n:
            raise UnknownNodeErro("未知结点编号: %r" % (u,))

    # ------------------------------------------------------------------
    # 朴素口径: 逐结点重走子树
    # ------------------------------------------------------------------
    def _heaviest_child(self, u):
        """按子树节点数挑重儿子，并列取编号最小者。

        空儿子返回 None。
        """
        best = None
        best_key = None
        for w in self._children[u]:
            key = (self._size[w], -w)
            if best_key is None or key > best_key:
                best_key = key
                best = w
        return best

    def heuristic_child(self, u):
        """返回 u 的重儿子编号（按子树节点数口径），无儿子返回 None。"""
        self._check_loaded()
        self._check_node(u)
        return self._heaviest_child(u)

    def _depth_counts(self, u):
        """返回 u 子树内每个深度的节点个数，下标即相对深度。

        朴素做法：先对每个儿子递归求出深度数组，再新建一份长度足够的
        数组，把儿子数组逐个元素拷贝相加，最后把自己计入深度零。
        """
        children = self._children[u]
        if not children:
            return [1]
        merged = [0]
        for w in children:
            sub = self._depth_counts(w)
            if len(merged) < len(sub) + 1:
                grown = [0] * (len(sub) + 1)
                for i in range(len(merged)):
                    grown[i] = merged[i]
                merged = grown
            for i in range(len(sub)):
                merged[i + 1] += sub[i]
        merged[0] = 1
        return merged

    def depth_counts(self, u):
        """返回 u 子树内每个深度的节点个数列表，下标为相对深度。"""
        self._check_loaded()
        self._check_node(u)
        return list(self._depth_counts(u))

    def deepest_depth(self, u):
        """返回 u 子树内最深节点的深度（相对 u 自身为 0）。"""
        self._check_loaded()
        self._check_node(u)
        return len(self._depth_counts(u)) - 1

    def depth_distribution(self):
        """返回全树内每个深度的节点个数列表，下标为绝对深度。"""
        self._check_loaded()

        def rec(u):
            children = self._children[u]
            if not children:
                return [1]
            merged = [0]
            for w in children:
                sub = rec(w)
                if len(merged) < len(sub) + 1:
                    grown = [0] * (len(sub) + 1)
                    for i in range(len(merged)):
                        grown[i] = merged[i]
                    merged = grown
                for i in range(len(sub)):
                    merged[i + 1] += sub[i]
            merged[0] = 1
            return merged

        return rec(0)

    def merge_cost(self):
        """返回朴素口径下逐结点归并深度数组时的元素拷贝总次数估计。

        每个结点归并各儿子数组时，要把儿子数组整份拷进一张新数组，
        此处按所有结点各次合并所搬运的元素个数求和。
        """
        self._check_loaded()
        total = 0

        def rec(u):
            children = self._children[u]
            if not children:
                return 1
            merged_len = 1
            for w in children:
                sub_len = rec(w)
                # 新建长度为 sub_len + 1 的数组并把各元素拷入，再搬回并入
                total_cost = (sub_len + 1) + sub_len
                nonlocal total
                total += total_cost
                if merged_len < sub_len + 1:
                    merged_len = sub_len + 1
            merged_len = max(merged_len, 1)
            return merged_len

        rec(0)
        return total

    def node_count(self):
        """返回结点个数。"""
        self._check_loaded()
        return self._n
