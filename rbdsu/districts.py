"""改造前的朴素并查集：搬到动方、回滚整表重算。

现状口径是这样的：每个集合把成员逐个放进一张列表里保存，合并两个集合时，
固定把前一方的全部成员逐个搬进后一方的成员列表，再把空掉的成员列表丢掉；
每次回滚都把整张成员表从当前父指针关系重新走一遍、重建出全部集合。规模一大，
合并与回滚都要把成员逐个搬来搬去，代价迅速退到平方甚至更高量级。

没有任何历史记录，回滚只能靠整表重算；连通判定与集合大小都从成员列表里数，
结果虽然对，但集合一多一大就明显变慢。纯标准库，无外部依赖。
"""

__all__ = [
    "RollbackDSU",
    "Erro",
    "DsuInputError",
    "UnknownElemError",
    "NoCheckpointError",
]


class Erro(Exception):
    """本模块所有异常的基类。"""


class DsuInputError(Erro):
    """元素个数或标签取值不合法。"""


class UnknownElemError(Erro):
    """查询引用了不在本结构里的元素。"""


class NoCheckpointError(Erro):
    """按时间点回滚时找不到对应的检查点。"""


class RollbackDSU:
    """支持合并、连通查询、集合大小与整体回滚的朴素并查集。

    内部维护一张成员表，键是集合代表，值是该集合全体成员的列表；回滚时把
    成员表按当前父指针关系整表重算。模块级不持有任何可变状态，同一份固定
    输入重复运行结果一致。
    """

    def __init__(self, n, labels=None):
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise DsuInputError("元素个数必须是非负整数")
        if labels is None:
            labels = [str(i) for i in range(n)]
        if len(labels) != n:
            raise DsuInputError("标签个数与元素个数不符")
        for lb in labels:
            if not isinstance(lb, str) or not lb:
                raise DsuInputError("标签必须是非空字符串")
        self._n = n
        self._label = list(labels)
        self._names = {lb: i for i, lb in enumerate(self._label)}
        self._parent = list(range(n))
        self._members = {i: [i] for i in range(n)}
        self._history = [list(self._parent)]

    # ------------------------------------------------------------------
    # 基本查询
    # ------------------------------------------------------------------
    def _find(self, x):
        """朴素查找：顺着父指针一路走到根，不做任何压缩。"""
        while self._parent[x] != x:
            x = self._parent[x]
        return x

    def count(self):
        """返回当前元素总数。"""
        return self._n

    def connected(self, a, b):
        """判断两个元素当前是否在同一集合里。"""
        return self._find(self._resolve(a)) == self._find(self._resolve(b))

    def size(self, elem):
        """返回元素所在集合的成员个数，从成员列表里数。"""
        root = self._find(self._resolve(elem))
        return len(self._members.get(root, []))

    def members(self, elem):
        """返回元素所在集合的成员名列表副本，按名字排好序。"""
        root = self._find(self._resolve(elem))
        return sorted(self._label[i] for i in self._members.get(root, []))

    def group_count(self):
        """返回当前集合个数。"""
        return len(self._collect_groups())

    def groups(self):
        """返回全部集合，每个集合是排好序的成员名列表，整体按首名排序。"""
        return self._collect_groups()

    # ------------------------------------------------------------------
    # 合并：把动方成员逐个搬进静方成员表
    # ------------------------------------------------------------------
    def union(self, a, b):
        """合并两个元素所在的集合，已同集合则按无操作处理。

        朴素做法：把 a 所在集合的成员逐个搬进 b 所在集合的成员列表。
        """
        ra = self._find(self._resolve(a))
        rb = self._find(self._resolve(b))
        if ra == rb:
            return False
        moving = self._members.get(ra, [])
        target = self._members.get(rb, [])
        for m in moving:
            target.append(m)
            self._parent[m] = rb
        self._members[ra] = []
        self._members[rb] = sorted(target)
        return True

    def checkout(self):
        """打一个检查点，返回该时间点的整数标识。"""
        self._history.append(list(self._parent))
        return len(self._history) - 1

    def rollback(self, point):
        """回滚到指定时间点那一刻的状态。

        朴素做法：先把父指针恢复到检查点，再把整张成员表从父指针关系
        从头重算一遍、重建出全部集合，随后丢弃该点之后的历史。
        """
        if not isinstance(point, int) or isinstance(point, bool):
            raise NoCheckpointError("时间点必须是整数")
        if point < 0 or point >= len(self._history):
            raise NoCheckpointError("找不到对应的时间点")
        self._parent = list(self._history[point])
        self._rebuild_members()
        del self._history[point + 1:]
        return self

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _collect_groups(self):
        """按当前成员表整理出全部集合。"""
        out = []
        for root in sorted(self._members):
            rows = self._members.get(root)
            if rows:
                out.append(sorted(self._label[i] for i in rows))
        out.sort()
        return out

    def _rebuild_members(self):
        """按当前父指针关系整表重算成员表。"""
        self._members = {}
        for i in range(self._n):
            root = self._find(i)
            self._members.setdefault(root, []).append(i)
        for r in list(self._members):
            self._members[r] = sorted(self._members[r])

    def _resolve(self, elem):
        """把元素名解析成物理编号。"""
        if isinstance(elem, str) and elem in self._names:
            return self._names[elem]
        if isinstance(elem, int) and not isinstance(elem, bool) and 0 <= elem < self._n:
            return elem
        raise UnknownElemError("未知元素: %r" % (elem,))
