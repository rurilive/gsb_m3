"""朴素组合与排列枚举实现 NaiveEnumerator。

改造前的基线：给定集合规模，用最直白的递归逐位展开，
每一位都在一个还没有用过的元素列表里做线性查找，
进而求出组合数、排列数、全部组合、全部全排列，
再给出按字典序取第几个、以及判断某个序列的名次。

结果正确，但代价随规模阶乘级上涨，而且名次与序号之间
没有解析互逆公式，只能靠现场从头展开顺带数出来。

纯标准库，无外部依赖。
"""

from itertools import combinations, permutations


class CombPermError(Exception):
    """组合与排列库的参数错误基类。"""


class NaiveEnumerator:
    """朴素枚举器：以规模为核心参数，逐位递归展开全部结果。

    约定：
    集合恒为整数序列 0 到 规模减一，下标从零开始，字典序按元素大小排列。
    名次与序号一律从零开始计数，即字典序第一个结果的名次与序号都是零。
    """

    def __init__(self, size):
        if isinstance(size, bool) or not isinstance(size, int):
            raise CombPermError("规模必须是整数")
        if size < 0:
            raise CombPermError("规模必须是非负整数")
        self._size = size

    def size(self):
        """集合规模。"""
        return self._size

    def _universe(self):
        """当前规模下的有序全集。"""
        return list(range(self._size))

    def _validate_k(self, k):
        if isinstance(k, bool) or not isinstance(k, int):
            raise CombPermError("选取个数必须是整数")
        if k < 0 or k > self._size:
            raise CombPermError("选取个数必须在零与规模之间")

    def combinations_count(self, k):
        """从规模个元素里取 k 个的组合数。k 越界抛出 CombPermError。"""
        self._validate_k(k)
        if k == 0:
            return 1
        return len(self.all_combinations(k))

    def permutations_count(self, k):
        """从规模个元素里取 k 个的排列数。k 越界抛出 CombPermError。"""
        self._validate_k(k)
        if k == 0:
            return 1
        return len(self.all_permutations(k))

    def all_combinations(self, k):
        """全部组合，按字典序。k 越界抛出 CombPermError。"""
        self._validate_k(k)
        return [tuple(c) for c in combinations(self._universe(), k)]

    def all_permutations(self, k):
        """全部 k 元排列，按字典序。k 越界抛出 CombPermError。"""
        self._validate_k(k)
        return [tuple(p) for p in permutations(self._universe(), k)]

    def _expand(self, items):
        """最直白的递归：逐位挑选尚未用过的元素。"""
        if not items:
            return [()]
        used = []
        for x in items:
            rest = [y for y in items if y != x]
            for tail in self._expand(rest):
                used.append((x,) + tail)
        return used

    def _linear_used_expand(self, k):
        """按位展开，维护已用元素列表，取下一个元素时做线性查找。"""
        universe = self._universe()
        out = []

        def walk(prefix, used):
            if len(prefix) == k:
                out.append(tuple(prefix))
                return
            for x in universe:
                if x in used:
                    continue
                used.append(x)
                prefix.append(x)
                walk(prefix, used)
                prefix.pop()
                used.pop()

        walk([], [])
        return out

    def _ordered_tuples(self, k, mode):
        """按字典序返回 k 元组合或排列；组合逐位递增，排列逐位不限。"""
        if mode == "comb":
            return self.all_combinations(k)
        return self.all_permutations(k)

    def nth(self, k, index, mode="perm"):
        """按字典序取第 index 个组合或排列，序号从零开始。

        mode 取组合或排列其一，越界或模式非法抛出 CombPermError。
        基线的做法就是先展开全部结果再按序号取值。
        """
        if mode not in ("comb", "perm"):
            raise CombPermError("模式只能是组合或排列")
        self._validate_k(k)
        ordered = self._ordered_tuples(k, mode)
        if isinstance(index, bool) or not isinstance(index, int):
            raise CombPermError("序号必须是整数")
        if index < 0 or index >= len(ordered):
            raise CombPermError("序号越界")
        return ordered[index]

    def rank(self, seq, mode="perm"):
        """给出某个序列在字典序里的名次，名次从零开始。

        mode 取组合或排列其一；序列非法或不存在抛出 CombPermError。
        """
        if mode not in ("comb", "perm"):
            raise CombPermError("模式只能是组合或排列")
        if not isinstance(seq, (list, tuple)):
            raise CombPermError("序列必须是列表或元组")
        seq = tuple(seq)
        k = len(seq)
        self._validate_k(k)
        for x in seq:
            if isinstance(x, bool) or not isinstance(x, int):
                raise CombPermError("序列元素必须是整数")
            if x < 0 or x >= self._size:
                raise CombPermError("序列元素越界")
        if len(set(seq)) != len(seq):
            raise CombPermError("序列元素不许重复")
        ordered = self._ordered_tuples(k, mode)
        if mode == "comb" and list(seq) != sorted(seq):
            raise CombPermError("组合的元素必须递增")
        if seq not in ordered:
            raise CombPermError("序列不在该模式的字典序中")
        return ordered.index(seq)
