"""差分约束系统的朴素实现。

现状能力：把一批形如 x减y不超过常数、x减y恰好等于常数的约束收进来，
用最直白的做法给出结果——求解时对全部约束反复扫描、逐轮松弛每个变量，
直到某一轮不再有任何变化；求两个变量差的最大值时也照同一套松弛来做。

这套做法规模一大就慢：每轮都要把每条约束都看一遍，轮数又随变量数增长，
变量或约束一多就明显变慢，但结果是对的。
"""


class DiffError(Exception):
    """差分约束相关异常的基类。"""


class ConstraintError(DiffError):
    """约束登记期入参非法（变量名、上界或关系不合法）。"""


class Infeasible(DiffError):
    """约束系统无解，即约束图上存在负环。"""


class Constraint:
    """一条差分约束。

    op 取 le 表示 x l 减 x r 不超过 bound；取 eq 表示两者恰好等于 bound。
    """

    __slots__ = ("lhs", "rhs", "op", "bound")

    def __init__(self, lhs, rhs, op, bound):
        self.lhs = lhs
        self.rhs = rhs
        self.op = op
        self.bound = bound

    def __repr__(self):
        sign = "<=" if self.op == "le" else "=="
        return "Constraint(%r, %r, %r, %r)" % (self.lhs, self.rhs, sign, self.bound)

    def __eq__(self, other):
        if not isinstance(other, Constraint):
            return NotImplemented
        return (self.lhs, self.rhs, self.op, self.bound) == (
            other.lhs, other.rhs, other.op, other.bound)

    def __hash__(self):
        return hash((self.lhs, self.rhs, self.op, self.bound))


def _check_name(value):
    if not isinstance(value, str) or not value:
        raise ConstraintError("变量名必须是非空字符串：%r" % (value,))


def _check_bound(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConstraintError("上界必须是整数：%r" % (value,))


class DifferenceSystem:
    """一批差分约束的集合，提供朴素求解与校验。"""

    def __init__(self):
        self._items = []
        self._names = set()

    # ---- 登记 ----

    def add_le(self, lhs, rhs, bound):
        """登记 x[lhs] 减 x[rhs] 不超过 bound 的约束。"""
        _check_name(lhs)
        _check_name(rhs)
        _check_bound(bound)
        c = Constraint(lhs, rhs, "le", bound)
        self._register(c)
        return c

    def add_eq(self, lhs, rhs, bound):
        """登记 x[lhs] 减 x[rhs] 恰好等于 bound 的约束。"""
        _check_name(lhs)
        _check_name(rhs)
        _check_bound(bound)
        c = Constraint(lhs, rhs, "eq", bound)
        self._register(c)
        return c

    def _register(self, c):
        self._items.append(c)
        self._names.add(c.lhs)
        self._names.add(c.rhs)

    def constraints(self):
        """按登记顺序返回全部约束。"""
        return list(self._items)

    def variables(self):
        """返回出现过的变量名，按字典序升序。"""
        return sorted(self._names)

    def __len__(self):
        return len(self._items)

    # ---- 朴素求解 ----

    def _edges(self):
        """把约束摊平成松弛用的有向边 (u, v, w)，含义为 x[v] 减 x[u] 不超过 w。"""
        edges = []
        for c in self._items:
            if c.op == "le":
                edges.append((c.rhs, c.lhs, c.bound))
            else:
                edges.append((c.rhs, c.lhs, c.bound))
                edges.append((c.lhs, c.rhs, -c.bound))
        return edges

    def solve(self):
        """朴素反复松弛，返回一组可行赋值；无解抛 Infeasible。"""
        names = self.variables()
        if not names:
            return {}
        value = {name: 0 for name in names}
        edges = self._edges()
        limit = len(names)
        for _ in range(limit + 1):
            changed = False
            for u, v, w in edges:
                if value[v] > value[u] + w:
                    value[v] = value[u] + w
                    changed = True
            if not changed:
                for u, v, w in edges:
                    if value[v] > value[u] + w:
                        raise Infeasible("约束在反复松弛后仍不收敛，约束图上有负环")
                return value
        raise Infeasible("约束在反复松弛后仍不收敛，约束图上有负环")

    def has_solution(self):
        """有没有可行解。"""
        try:
            self.solve()
        except Infeasible:
            return False
        return True

    def diff_max(self, a, b):
        """x[a] 减 x[b] 的最大可能值；没有上界时返回 None。"""
        _check_name(a)
        _check_name(b)
        names = self.variables()
        if a not in self._names or b not in self._names:
            return None
        edges = self._edges()
        infinity = float("inf")
        dist = {name: infinity for name in names}
        dist[b] = 0
        for _ in range(len(names) + 1):
            changed = False
            for u, v, w in edges:
                if dist[u] != infinity and dist[v] > dist[u] + w:
                    dist[v] = dist[u] + w
                    changed = True
            if not changed:
                break
        if dist[a] == infinity:
            return None
        return dist[a]

    # ---- 赋值校验 ----

    def check_assignment(self, assignment):
        """逐一核对赋值是否满足全部约束，返回第一条被违反的约束，全满足返回 None。"""
        if not isinstance(assignment, dict):
            raise ConstraintError("赋值必须是字典：%r" % (assignment,))
        for name in self.variables():
            if name not in assignment:
                raise ConstraintError("赋值缺少变量：%r" % (name,))
            value = assignment[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConstraintError("变量取值必须是整数：%r" % (value,))
        for c in self._items:
            delta = assignment[c.lhs] - assignment[c.rhs]
            if c.op == "le":
                if delta > c.bound:
                    return c
            elif delta != c.bound:
                return c
        return None
