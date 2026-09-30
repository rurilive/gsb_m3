"""treeknapsack.knapsack：树形依赖选择工具包（改造前基线，朴素实现）。

当前只有朴素路子，全部依赖"枚举加判定"：

  - 求根节点最优价值时，从空集开始逐个考虑物品的选与不选，只在依赖闭合（选了某个
    物品，它的祖先都已选）时才往下走，其余全部剪掉；
  - 依赖闭合判定自己走一遍每个已选物品到根的路径；
  - 求每个子树在给定容量下的最优价值时，逐个把子树取满，再对子树内每个节点单独
    再枚举一遍节点的取几件组合，子树一大就成指数级爆炸；
  - 森林与多棵根整棵整棵地并起来处理；
  - 所有计数都按次累加，随调用规模增长。

朴素但正确，规模一大就慢，是留给升级路径对账的锚。
"""

from enum import Enum

MAX_CAP = 24
MAX_ITEMS = 14


class Erro(Exception):
    """全部错误的基类，上层只认这一个根。"""


class SizeErro(Erro):
    """规模超出上限或数值不合法。"""


class GraphErro(Erro):
    """父指针构不成合法森林。"""


class WeightErro(Erro):
    """重量或价值不合法。"""


class CapacityErro(Erro):
    """容量口径不合法。"""


class Metric(Enum):
    """树形背包的两种容量口径。"""

    EXACT = "exact"
    AT_MOST = "at_most"


class TreeKnapsack(object):
    """树形依赖选择工具包，当前为朴素枚举基线。

    物品以编号标识，父指针给出树结构；容量为背包总重上限。全部结果只由入参决定，
    不依赖模块级可变状态；每次计算前先把它自己的计数归零。
    """

    def __init__(self, n, parent, weight, value, cap):
        self._check_n(n)
        self.n = n
        self._check_parent(parent)
        self.parent = self._normalize_parent(parent)
        self._check_weight(weight)
        self.weight = list(weight)
        self._check_value(value)
        self.value = list(value)
        self._check_cap(cap)
        self.cap = cap
        self.children = self._build_children()
        self.roots = [i for i in range(n) if self.parent[i] == -1]
        self.brute_visits = 0

    # ---- 校验 ------------------------------------------------------------

    def _is_int(self, x):
        return isinstance(x, int) and not isinstance(x, bool)

    def _check_n(self, n):
        if not self._is_int(n):
            raise SizeErro("n 必须是非负整数")
        if n < 0:
            raise SizeErro("n 不能为负")
        if n > MAX_ITEMS:
            raise SizeErro("物品数超过上限 %d" % MAX_ITEMS)

    def _check_parent(self, parent):
        if not isinstance(parent, (list, tuple)):
            raise SizeErro("父指针必须是序列")
        if len(parent) != self.n:
            raise SizeErro("父指针长度必须与物品数一致")
        for p in parent:
            if not self._is_int(p):
                raise GraphErro("父指针必须是整数")
            if p < -1 or p >= self.n:
                raise GraphErro("父指针越界")
        for i, p in enumerate(parent):
            if p == i:
                raise GraphErro("物品不能以自身为父")

    def _normalize_parent(self, parent):
        parent = list(parent)
        state = [0] * self.n
        for i in range(self.n):
            if state[i] == 2:
                continue
            chain = []
            j = i
            while j != -1 and state[j] == 0:
                state[j] = 1
                chain.append(j)
                j = parent[j]
            if j != -1 and state[j] == 1:
                raise GraphErro("父指针成环")
            for node in chain:
                state[node] = 2
        return parent

    def _check_weight(self, weight):
        if not isinstance(weight, (list, tuple)):
            raise WeightErro("重量必须是序列")
        if len(weight) != self.n:
            raise WeightErro("重量长度必须与物品数一致")
        for w in weight:
            if not self._is_int(w):
                raise WeightErro("重量必须是整数")
            if w < 0:
                raise WeightErro("重量不能为负")

    def _check_value(self, value):
        if not isinstance(value, (list, tuple)):
            raise WeightErro("价值必须是序列")
        if len(value) != self.n:
            raise WeightErro("价值长度必须与物品数一致")
        for v in value:
            if not self._is_int(v):
                raise WeightErro("价值必须是整数")

    def _check_cap(self, cap):
        if not self._is_int(cap):
            raise CapacityErro("容量必须是整数")
        if cap < 0:
            raise CapacityErro("容量不能为负")

    def _build_children(self):
        children = [[] for _ in range(self.n)]
        for i in range(self.n):
            if self.parent[i] != -1:
                children[self.parent[i]].append(i)
        return children

    def _zero(self):
        self.brute_visits = 0

    # ---- 依赖闭合判定 ----------------------------------------------------

    def _is_closed(self, chosen):
        """把每个已选物品沿父指针走到根，逐个检查祖先是否都已选。"""
        chosen_set = set(chosen)
        for item in chosen:
            j = self.parent[item]
            while j != -1:
                if j not in chosen_set:
                    return False
                j = self.parent[j]
        return True

    # ---- 朴素枚举 --------------------------------------------------------

    def _enumerate(self, capacity=None):
        """逐个考虑物品选与不选，累积重量与价值，记录最优。"""
        if capacity is None:
            capacity = self.cap
        n = self.n
        visit = self.brute_visits
        best = [None, None]

        def rec(idx, cur_w, cur_v, chosen):
            nonlocal visit
            if cur_w > capacity:
                return
            if idx == n:
                if not self._is_closed(chosen):
                    return
                if best[0] is None or cur_v > best[0]:
                    best[0] = cur_v
                    best[1] = sorted(chosen)
                elif cur_v == best[0]:
                    cand = sorted(chosen)
                    if cand < best[1]:
                        best[1] = cand
                return
            visit += 1
            rec(idx + 1, cur_w, cur_v, chosen)
            rec(idx + 1, cur_w + self.weight[idx], cur_v + self.value[idx],
                chosen + [idx])

        rec(0, 0, 0, [])
        self.brute_visits = visit
        return best[0], best[1]

    def brute_best(self, capacity=None):
        """根节点最优价值与选中的物品集合（并列取节点编号字典序最小）。"""
        self._zero()
        value, chosen = self._enumerate(capacity)
        if chosen is None:
            return 0, []
        return value, chosen

    def brute_exact(self, cap):
        """恰好选满容量 cap 时的最优价值与物品集合，选不满返回 None 与空表。"""
        self._check_cap(cap)
        self._zero()
        n = self.n
        visit = self.brute_visits
        best = [None, None]

        def rec(idx, cur_w, cur_v, chosen):
            nonlocal visit
            if cur_w > cap:
                return
            if idx == n:
                if cur_w == cap and self._is_closed(chosen):
                    if best[0] is None or cur_v > best[0]:
                        best[0] = cur_v
                        best[1] = sorted(chosen)
                    elif cur_v == best[0] and sorted(chosen) < best[1]:
                        best[1] = sorted(chosen)
                return
            visit += 1
            rec(idx + 1, cur_w, cur_v, chosen)
            rec(idx + 1, cur_w + self.weight[idx], cur_v + self.value[idx],
                chosen + [idx])

        rec(0, 0, 0, [])
        self.brute_visits = visit
        if best[0] is None:
            return None, []
        return best[0], best[1]

    # ---- 每个子树的最优价值 ----------------------------------------------

    def brute_subtree(self, root, cap):
        """子树 root 在容量 cap 下的最优价值与物品集合（不超容量口径）。

        允许一件不选，最优价值下界为零；并列时取节点编号字典序最小的集合。
        """
        self._check_cap(cap)
        if not self._is_int(root) or root < 0 or root >= self.n:
            raise SizeErro("子树根越界")
        self._zero()
        nodes = self._collect(root)
        m = len(nodes)
        visit = 0
        best = [0, []]

        node_set = set(nodes)

        def closed(chosen):
            chosen_set = set(nodes[i] for i in chosen)
            for i in chosen:
                j = self.parent[nodes[i]]
                while j != -1 and j in node_set:
                    if j not in chosen_set:
                        return False
                    j = self.parent[j]
            return True

        def rec(k, cur_w, cur_v, chosen):
            nonlocal visit
            if cur_w > cap:
                return
            if k == m:
                if not closed(chosen):
                    return
                cand = sorted(nodes[i] for i in chosen)
                if cur_v > best[0]:
                    best[0] = cur_v
                    best[1] = cand
                elif cur_v == best[0] and cand < best[1]:
                    best[1] = cand
                return
            visit += 1
            rec(k + 1, cur_w, cur_v, chosen)
            item = nodes[k]
            rec(k + 1, cur_w + self.weight[item], cur_v + self.value[item],
                chosen + [k])

        rec(0, 0, 0, [])
        self.brute_visits = visit
        return best[0], best[1]

    def brute_all_subtrees(self, cap):
        """每个节点作为子树根，在容量 cap 下的最优价值，按编号升序。"""
        self._check_cap(cap)
        return [self.brute_subtree(i, cap)[0] for i in range(self.n)]

    def _collect(self, root):
        order = []
        stack = [root]
        while stack:
            u = stack.pop()
            order.append(u)
            stack.extend(reversed(self.children[u]))
        return order

    # ---- 森林 ------------------------------------------------------------

    def forest_count(self):
        """根节点个数。"""
        return len(self.roots)

    def is_forest(self):
        """是否为空树或森林（根节点不止一个）。"""
        return self.n == 0 or len(self.roots) > 1
