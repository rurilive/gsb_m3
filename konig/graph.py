"""konig.graph：改造前的朴素二分图工具（基线）。

左侧一组点，右侧一组点，边用有序对逐条登记。只有两项朴素能力：

- 求最大匹配：对每个左侧点用最直白的深度优先增广路搜索，路径上
  走到哪算哪，不做任何剪枝与优化，找到一条就翻转配对，找不到就
  换下一个起点。
- 求点覆盖：直接枚举左侧点里该选的子集，每个子集都逐条验证是否
  盖住全部边，只取规模最小的那个。注意这条朴素路径只允许从左点
  里挑，完全没有考虑右点，因此挑出来的覆盖未必是真正的最小覆盖。

两项能力的结果都正确，但规模一大、边一密，枚举与重复搜索的量就
指数级膨胀，稍大的图根本跑不动。
"""

import itertools


class KonigError(Exception):
    """konig 工具的异常基类。"""


class IllegalPointError(KonigError):
    """登记了空点或非法点。"""


class SelfLoopError(KonigError):
    """登记了连接同一个点的自环。"""


class DuplicateEdgeError(KonigError):
    """重复登记了同一条边（含重边）。"""


class UnknownPointError(KonigError):
    """引用了未在图中出现过的点。"""


class NotMatchedError(KonigError):
    """请求的左侧点当前没有配到任何右侧点。"""


class NaiveGraph:
    """朴素二分图：求匹配靠增广路深搜，求点覆盖靠子集枚举。"""

    def __init__(self, left=None, right=None):
        self._left = []
        self._right = []
        self._left_set = set()
        self._right_set = set()
        self._edges = []
        self._edge_set = set()
        self._adj = {}
        self._last_matching = None
        if left is not None:
            for name in left:
                self.add_left(name)
        if right is not None:
            for name in right:
                self.add_right(name)

    # ---- 建图 ----

    def _side(self, which):
        if which == "left":
            return self._left, self._left_set
        if which == "right":
            return self._right, self._right_set
        raise KonigError("侧别只能是 left 或 right")

    def add_left(self, name):
        names, seen = self._side("left")
        if not isinstance(name, str) or not name:
            raise IllegalPointError("左侧点名必须是非空字符串")
        if name in seen:
            return self
        seen.add(name)
        names.append(name)
        self._adj[name] = []
        return self

    def add_right(self, name):
        names, seen = self._side("right")
        if not isinstance(name, str) or not name:
            raise IllegalPointError("右侧点名必须是非空字符串")
        if name in seen:
            return self
        seen.add(name)
        names.append(name)
        return self

    def add_edge(self, left, right):
        if not isinstance(left, str) or not left:
            raise IllegalPointError("左侧点名必须是非空字符串")
        if not isinstance(right, str) or not right:
            raise IllegalPointError("右侧点名必须是非空字符串")
        if left not in self._left_set:
            raise UnknownPointError("未知的左侧点: %s" % (left,))
        if right not in self._right_set:
            raise UnknownPointError("未知的右侧点: %s" % (right,))
        if left == right:
            raise SelfLoopError("不允许自环: %s" % (left,))
        if (left, right) in self._edge_set:
            raise DuplicateEdgeError("重复的边: %s-%s" % (left, right))
        self._edge_set.add((left, right))
        self._edges.append((left, right))
        self._adj[left].append(right)
        return self

    def left_points(self):
        return list(self._left)

    def right_points(self):
        return list(self._right)

    def edges(self):
        return list(self._edges)

    def edge_count(self):
        return len(self._edges)

    def neighbors(self, left):
        if left not in self._left_set:
            raise UnknownPointError(left)
        return list(self._adj[left])

    # ---- 朴素匹配 ----

    def naive_max_matching(self):
        """最直白的增广路搜索：每个左侧点深度优先找一条增广路，找到就翻转。"""
        match_l = {}
        match_r = {}

        def walk(left, visited):
            for right in self._adj[left]:
                if right in visited:
                    continue
                visited.add(right)
                holder = match_r.get(right)
                if holder is None or walk(holder, visited):
                    match_l[left] = right
                    match_r[right] = left
                    return True
            return False

        for left in self._left:
            walk(left, set())
        self._last_matching = dict(match_l)
        return [(left, match_l[left])
                for left in self._left if left in match_l]

    def naive_matching_size(self):
        return len(self.naive_max_matching())

    def matched_to(self, left):
        if left not in self._left_set:
            raise UnknownPointError(left)
        if self._last_matching is None:
            raise KonigError("尚未求出匹配方案")
        if left not in self._last_matching:
            raise NotMatchedError(left)
        return self._last_matching[left]

    # ---- 朴素点覆盖 ----

    def _covers_all(self, chosen):
        for left, right in self._edges:
            if left not in chosen:
                return False
        return True

    def naive_min_vertex_cover(self):
        """枚举左侧点的子集，取能盖住全部边的最小者，只从左点里挑。"""
        best = None
        for size in range(len(self._left) + 1):
            chosen = [combo for combo in itertools.combinations(self._left, size)
                      if self._covers_all(set(combo))]
            if chosen:
                best = min(chosen, key=lambda combo: tuple(sorted(combo)))
                break
        return sorted(best) if best is not None else []

    def naive_cover_size(self):
        return len(self.naive_min_vertex_cover())
