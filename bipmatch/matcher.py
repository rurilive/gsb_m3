"""bipmatch.matcher: 改造前的朴素二分图匹配器。

现状是一个只求最大匹配的朴素实现 NaiveMatcher：

- 左侧顶点按登记顺序逐个处理，每个左顶点都跑一遍增广路暴力搜索；
- 找增广路用深搜加逐点回溯，找到就把路径上的配对翻转；
- 找不到就跳过这个左顶点，继续下一个；
- 对同一张图甚至会整题重搜，直到某一轮没有任何增广为止；
- 只报匹配边数（size）与匹配边集（matching_edges）。

它不提供最小顶点覆盖，不做匹配是否最大的判定，也不记录搜索规模。
结果正确，但图一大、增广路一长，反复重搜就会很慢。
"""


class BipMatchError(Exception):
    """bipmatch 的业务异常基类。"""


class DuplicateEdgeError(BipMatchError):
    """重复登记了同一条边（含重边）。"""


class SelfLoopError(BipMatchError):
    """登记了连接同一个顶点的自环。"""


class CannotMatchError(BipMatchError):
    """请求的匹配在这张图上无法完成。"""


class NaiveMatcher:
    """朴素二分图匹配器。

    约定：左侧顶点名与右侧顶点名同名也算不同顶点，两侧各建一张名字表。
    """

    def __init__(self, left=None, right=None):
        self._left = []
        self._right = []
        self._left_set = set()
        self._right_set = set()
        self._edges = []
        self._edge_set = set()
        if left is not None:
            for name in left:
                self.add_left(name)
        if right is not None:
            for name in right:
                self.add_right(name)

    # ---- 建图 ----

    def _team(self, side):
        if side == "left":
            return self._left, self._left_set
        if side == "right":
            return self._right, self._right_set
        raise BipMatchError("侧别只能是 left 或 right")

    def add_left(self, name):
        names, seen = self._team("left")
        if not isinstance(name, str) or not name:
            raise BipMatchError("顶点名必须是非空字符串")
        if name in seen:
            return
        seen.add(name)
        names.append(name)

    def add_right(self, name):
        names, seen = self._team("right")
        if not isinstance(name, str) or not name:
            raise BipMatchError("顶点名必须是非空字符串")
        if name in seen:
            return
        seen.add(name)
        names.append(name)

    def add_edge(self, left, right):
        if left not in self._left_set:
            raise CannotMatchError("未知的左侧顶点: %s" % (left,))
        if right not in self._right_set:
            raise CannotMatchError("未知的右侧顶点: %s" % (right,))
        if left == right:
            raise SelfLoopError("不允许自环: %s" % (left,))
        if (left, right) in self._edge_set:
            raise DuplicateEdgeError("重复的边: %s-%s" % (left, right))
        self._edge_set.add((left, right))
        self._edges.append((left, right))

    def left_nodes(self):
        return list(self._left)

    def right_nodes(self):
        return list(self._right)

    def edges(self):
        return list(self._edges)

    def adjacency(self):
        """左顶点名 -> 右侧邻居列表，按右侧登记顺序。"""
        adj = {name: [] for name in self._left}
        for left, right in self._edges:
            adj[left].append(right)
        return adj

    # ---- 朴素匹配 ----

    def _search_augmenting(self, adj, left_to_right, right_to_left):
        """逐个左顶点深搜找增广路，找到就把配对翻转，返回是否找到。"""
        seen = set()
        for start in self._left:
            if start in left_to_right:
                continue
            stack = [(start, 0, [])]
            while stack:
                node, pos, path = stack.pop()
                if pos < len(adj[node]):
                    stack.append((node, pos + 1, path))
                    nxt = adj[node][pos]
                    if nxt in seen:
                        continue
                    seen.add(nxt)
                    if nxt in right_to_left:
                        stack.append((right_to_left[nxt], 0, path + [(node, nxt)]))
                    else:
                        for a, b in path + [(node, nxt)]:
                            left_to_right[a] = b
                            right_to_left[b] = a
                        return True
        return False

    def maximum_matching(self):
        """反复整题重搜，直到某轮再无增广为止。"""
        adj = self.adjacency()
        left_to_right = {}
        right_to_left = {}
        while self._search_augmenting(adj, left_to_right, right_to_left):
            pass
        return left_to_right, right_to_left

    def match(self):
        """返回最大匹配的边数。"""
        left_to_right, _ = self.maximum_matching()
        return len(left_to_right)

    def matching_edges(self):
        """返回最大匹配的边集，按左侧登记顺序。"""
        left_to_right, _ = self.maximum_matching()
        return [(left, left_to_right[left])
                for left in self._left if left in left_to_right]
