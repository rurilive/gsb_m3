"""matchx.bipartite：朴素二分图匹配与组合结构（改造前基线）。

左侧一个点集，右侧一个点集，边用 (左点, 右点) 集合表示，屏蔽重复边。
所有结果都由枚举驱动：

- max_matching_size()：回溯枚举全部匹配，取条数最多的一条
- is_maximum(matching)：枚举全部匹配，把给定匹配的大小与真正最大值比较
- perfect_matching_exists()：最大匹配是否覆盖全部左侧点
- min_vertex_cover()：枚举左右两侧点的全部子集，挑出能盖住每条边的
  最小点集
- max_independent_set()：枚举两个点集的全部子集，挑出内部没有任何边的
  最大点集

点数一多枚举量就撑不住，这里只保证口径正确，不追求快。
"""


class MatchError(Exception):
    """matchx 里所有可预期错误的基类。"""


class UnknownNodeError(MatchError):
    """引用了未在图中出现过的点。"""


class InvalidEdgeError(MatchError):
    """给了不合法的边，比如自环或空点。"""


class NotMatchedError(MatchError):
    """请求的左侧点当前没有配到任何右侧点。"""


def _key(node):
    """把点压成可排序、可哈希的表示，用来稳定枚举顺序。"""
    return type(node).__name__, repr(node)


class BipartiteMatcher:
    """朴素二分图匹配工具，结果一律靠枚举得到。"""

    def __init__(self):
        self._left = []
        self._right = []
        self._left_set = set()
        self._right_set = set()
        self._adj = {}
        self._edges = set()
        self._last = None

    # -- 建图 -------------------------------------------------------------

    def add_edge(self, left, right):
        """加一条从左侧点到右侧点的边，重复边只算一次，返回自身。"""
        if left is None or right is None:
            raise InvalidEdgeError("边的两端都不能为空: %r, %r" % (left, right))
        if left == right:
            raise InvalidEdgeError("自环不是合法边: %r" % (left,))
        self._register_left(left)
        self._register_right(right)
        self._adj[left].add(right)
        self._edges.add((left, right))
        return self

    def _register_left(self, left):
        if left not in self._left_set:
            self._left_set.add(left)
            self._left.append(left)
            self._adj[left] = set()

    def _register_right(self, right):
        if right not in self._right_set:
            self._right_set.add(right)
            self._right.append(right)

    @property
    def left_nodes(self):
        """全部左侧点，按首次出现顺序。"""
        return list(self._left)

    @property
    def right_nodes(self):
        """全部右侧点，按首次出现顺序。"""
        return list(self._right)

    def edges(self):
        """全部边，按端点排序后的稳定顺序。"""
        return sorted(self._edges, key=lambda e: (_key(e[0]), _key(e[1])))

    def edge_count(self):
        return len(self._edges)

    def node_count(self):
        return len(self._left) + len(self._right)

    def has_edge(self, left, right):
        return (left, right) in self._edges

    def neighbors(self, left):
        """左侧点连到的右侧点集合的副本。"""
        if left not in self._left_set:
            raise UnknownNodeError("左侧没有这个点: %r" % (left,))
        return set(self._adj[left])

    # -- 内部校验 ---------------------------------------------------------

    def _require_left(self, left):
        if left not in self._left_set:
            raise UnknownNodeError("左侧没有这个点: %r" % (left,))

    def _check_matching(self, matching):
        """校验一个方案确实是合法匹配，并返回左侧点到右侧点的字典。"""
        if not isinstance(matching, dict):
            raise MatchError("匹配方案必须是左侧点到右侧点的字典")
        used_right = set()
        checked = {}
        for left, right in matching.items():
            if left not in self._left_set:
                raise UnknownNodeError("左侧没有这个点: %r" % (left,))
            if right not in self._right_set:
                raise UnknownNodeError("右侧没有这个点: %r" % (right,))
            if not self.has_edge(left, right):
                raise MatchError("方案里有不存在的边: %r" % ((left, right),))
            if right in used_right:
                raise MatchError("同一个右侧点被配了两次: %r" % (right,))
            used_right.add(right)
            checked[left] = right
        return checked

    # -- 枚举求最大匹配 ---------------------------------------------------

    def _enumerate_matchings(self, on_matching):
        """回溯枚举全部匹配，每找到一条就交给 on_matching，返回枚举到的数量。

        左侧点按首次出现顺序逐个处理，每个点依次尝试配到尚未占用的右侧点，
        也允许不配，从而把所有匹配组合都走一遍。
        """
        order = list(self._left)
        total = 0
        cur = {}
        used = set()

        def rec(i):
            nonlocal total
            if i == len(order):
                total += 1
                on_matching(dict(cur))
                return
            left = order[i]
            for right in sorted(self._adj[left], key=_key):
                if right in used:
                    continue
                cur[left] = right
                used.add(right)
                rec(i + 1)
                del cur[left]
                used.discard(right)
            rec(i + 1)

        rec(0)
        return total

    def max_matching_size(self):
        """最大匹配条数：枚举全部匹配，取条数最多的那条。"""
        best = [0]

        def consider(matching):
            if len(matching) > best[0]:
                best[0] = len(matching)

        self._enumerate_matchings(consider)
        return best[0]

    def is_maximum(self, matching):
        """给定方案是否最大：枚举全部匹配，比大小。"""
        checked = self._check_matching(matching)
        return len(checked) == self.max_matching_size()

    def perfect_matching_exists(self):
        """是否存在覆盖全部左侧点的匹配。"""
        return self.max_matching_size() == len(self._left)

    # -- 枚举求最大匹配方案 -----------------------------------------------

    def max_matching(self):
        """返回一条条数最多的匹配方案，同分时取枚举顺序里先出现的那条。"""
        best = {"size": -1, "matching": {}}
        counter = [0]

        def consider(matching):
            counter[0] += 1
            if len(matching) > best["size"]:
                best["size"] = len(matching)
                best["matching"] = dict(matching)

        self._enumerate_matchings(consider)
        self._last = dict(best["matching"])
        return dict(best["matching"])

    def matched_to(self, left):
        """在最近一次求出的最大匹配里，返回左侧点配到的右侧点。"""
        self._require_left(left)
        if self._last is None:
            self.max_matching()
        if left not in self._last:
            raise NotMatchedError("左侧点没有配到右侧点: %r" % (left,))
        return self._last[left]

    # -- 枚举求最小点覆盖 -------------------------------------------------

    def _all_subsets(self, items):
        """按固定顺序枚举 items 的全部子集，从小到大、同类按序。"""
        n = len(items)
        for mask in range(1 << n):
            yield [items[i] for i in range(n) if mask & (1 << i)]

    def _is_vertex_cover(self, chosen):
        """点集是否盖住每一条边（每条边至少有一个端点在集合里）。"""
        cover = set(chosen)
        for left, right in self._edges:
            if left not in cover and right not in cover:
                return False
        return True

    def min_vertex_cover(self):
        """最小点覆盖：枚举两侧点的全部子集，挑最小的能盖住所有边的。"""
        universe = self.left_nodes + self.right_nodes
        best = None
        for chosen in self._all_subsets(universe):
            if best is not None and len(chosen) >= len(best):
                continue
            if self._is_vertex_cover(chosen):
                best = chosen
        return list(best) if best is not None else []

    # -- 枚举求最大独立集 -------------------------------------------------

    def _is_independent(self, chosen):
        """点集是否独立：集合内部没有任何一条边。"""
        inside = set(chosen)
        for left, right in self._edges:
            if left in inside and right in inside:
                return False
        return True

    def max_independent_set(self):
        """最大独立集：枚举全部子集，挑内部无边、元素最多的那个。"""
        universe = self.left_nodes + self.right_nodes
        best = []
        for chosen in self._all_subsets(universe):
            if len(chosen) <= len(best):
                continue
            if self._is_independent(chosen):
                best = chosen
        return list(best)
