"""unionfind 的朴素连通性工具。

现状是一套最直白的集合表示：内部用根到成员列表的字典维护各个集合，成员逐个存放。
合并两个集合时，把一侧的成员逐个搬进另一侧的列表里；查询归属时，逐个集合、逐个成员
地线性扫描；带权关系也是每搬一个成员就把它的偏移量重算一遍；回滚靠每次合并前整份
状态的深拷贝。口径单一、结果确定，但合并与查询一多就退化到平方量级，内存也随合并
次数线性膨胀。异常统一从 UnionFindError 派生。
"""


class UnionFindError(Exception):
    """本库所有异常的基类。"""


class UnionFindInputError(UnionFindError):
    """入参不合法，比如元素编号不是非负整数、偏移不是整数。"""


class UnknownNode(UnionFindError):
    """查询没有登记过的元素。"""


class NotConnected(UnionFindError):
    """求相对关系时两点不在同一个集合。"""


class IllegalRollback(UnionFindError):
    """回滚到越界的时刻。"""


class UnionFind:
    """朴素并查集：根到成员列表，逐元素搬移与线性扫描。"""

    def __init__(self):
        self._parent = {}
        self._members = {}
        self._diff = {}
        self._moves = 0
        self._visits = 0
        self._history = [self._snapshot()]

    # ---- 登记 ----

    def add(self, x):
        """登记元素，幂等；重复登记不改变已有归属。"""
        if not isinstance(x, int) or isinstance(x, bool) or x < 0:
            raise UnionFindInputError("元素编号必须是非负整数: %r" % (x,))
        if x in self._parent:
            return
        self._parent[x] = x
        self._members[x] = [x]
        self._diff[x] = 0

    def contains(self, x):
        return x in self._parent

    def elements(self):
        """全部已登记元素，升序。"""
        return sorted(self._parent)

    def _check(self, x):
        if x not in self._parent:
            raise UnknownNode("未登记的元素: %r" % (x,))

    # ---- 查询 ----

    def find(self, x):
        """返回元素所在集合的根，线性扫描全部集合与成员。"""
        self._check(x)
        for root, members in self._members.items():
            for m in members:
                self._visits += 1
                if m == x:
                    return root
        raise UnionFindError("内部状态不一致: %r" % (x,))

    def connected(self, a, b):
        """两点是否连通，同一点恒连通。"""
        self._check(a)
        self._check(b)
        return self.find(a) == self.find(b)

    def size(self, x):
        self._check(x)
        return len(self._members[self.find(x)])

    def rank(self, x):
        """集合高度，根到最远成员的距离，用朴素松弛逐轮推平。"""
        root = self.find(x)
        members = self._members[root]
        dist = {}
        for m in members:
            dist[m] = 0
        changed = True
        while changed:
            changed = False
            for m in members:
                p = self._parent[m]
                if p == m:
                    continue
                cand = dist[p] + 1
                if cand > dist[m]:
                    dist[m] = cand
                    changed = True
        return max(dist.values())

    def group_members(self, x):
        """某点所在集合的全部成员，升序。"""
        self._check(x)
        return sorted(self._members[self.find(x)])

    def groups(self):
        """全部集合，每个集合成员升序，集合之间按最小成员升序。"""
        out = [sorted(ms) for ms in self._members.values()]
        out.sort(key=lambda g: g[0])
        return out

    def component_count(self):
        return len(self._members)

    def component_sizes(self):
        return sorted(len(ms) for ms in self._members.values())

    # ---- 合并 ----

    def union(self, a, b):
        """把 b 所在集合的成员逐个搬进 a 所在集合，真正合并才返回真。"""
        self._check(a)
        self._check(b)
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return False
        moved = self._members[rb]
        target = self._members[ra]
        for m in moved:
            self._parent[m] = ra
            self._diff[m] = self._diff[m]
            target.append(m)
            self._moves += 1
        del self._members[rb]
        self._history.append(self._snapshot())
        return True

    def union_weighted(self, a, b, w):
        """在 a 与 b 之间建立关系，令 a 相对 b 的偏移恰为 w。"""
        if not isinstance(w, int) or isinstance(w, bool):
            raise UnionFindInputError("偏移必须是整数: %r" % (w,))
        self._check(a)
        self._check(b)
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return False
        # 目标: w(a) 减 w(b) 等于 w。设 k 为 b 的根相对 a 的根的偏移。
        k = self._diff[a] - self._diff[b] - w
        moved = self._members[rb]
        target = self._members[ra]
        for m in moved:
            self._parent[m] = ra
            self._diff[m] = self._diff[m] + k
            target.append(m)
            self._moves += 1
        del self._members[rb]
        self._history.append(self._snapshot())
        return True

    def relate(self, a, b):
        """返回 a 相对 b 的偏移，两点不同集合时抛 NotConnected。"""
        self._check(a)
        self._check(b)
        if self.find(a) != self.find(b):
            raise NotConnected("两点不在同一个集合: %r %r" % (a, b))
        return self._diff[a] - self._diff[b]

    # ---- 历史与回滚 ----

    def _snapshot(self):
        return {
            "parent": dict(self._parent),
            "members": {r: list(ms) for r, ms in self._members.items()},
            "diff": dict(self._diff),
            "moves": self._moves,
        }

    def _restore(self, snap):
        registered = set(self._parent)
        self._parent = dict(snap["parent"])
        self._members = {r: list(ms) for r, ms in snap["members"].items()}
        self._diff = dict(snap["diff"])
        self._moves = snap["moves"]
        for x in registered:
            if x not in self._parent:
                self._parent[x] = x
                self._members[x] = [x]
                self._diff[x] = 0

    def history_len(self):
        """已生效的合并次数。"""
        return len(self._history) - 1

    def undo(self):
        """撤销最近一次合并，空历史为无操作。"""
        if self.history_len() == 0:
            return False
        self.rollback_to(self.history_len() - 1)
        return True

    def rollback_to(self, t):
        """回到第 t 次合并之后，令 t 等于零即回到最初。"""
        if not isinstance(t, int) or isinstance(t, bool) or t < 0 or t > self.history_len():
            raise IllegalRollback("越界的时刻: %r" % (t,))
        self._restore(self._history[t])
        del self._history[t + 1:]

    def connected_at(self, t, a, b):
        """第 t 次合并之后两点是否连通，朴素地读回整份历史快照。"""
        self._check(a)
        self._check(b)
        if not isinstance(t, int) or isinstance(t, bool) or t < 0 or t > self.history_len():
            raise IllegalRollback("越界的时刻: %r" % (t,))
        snap = self._history[t]
        def root_of(x):
            for r, ms in snap["members"].items():
                for m in ms:
                    if m == x:
                        return r
            return None
        ra = root_of(a)
        rb = root_of(b)
        if ra is None or rb is None:
            return a == b
        return ra == rb

    # ---- 规模对照 ----

    def count_moves(self):
        """累计元素搬移次数。"""
        return self._moves

    def count_visits(self):
        """累计查询扫描的元素访问次数。"""
        return self._visits

    def cost_report(self):
        return {"moves": self._moves, "visits": self._visits}
