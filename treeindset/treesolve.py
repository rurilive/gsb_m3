"""改造前的朴素树求解器: 靠枚举每个顶点的选与不选来求最大独立集与最小点覆盖。

这是基线实现。维护一个无向的树 (加边时不检环), 要最大独立集或最小点覆盖时,
就用位掩码枚举每个顶点的选与不选共 2 的 n 次方种选法, 每一种都拿全部边逐对
核对: 选出的集合内部不能有边 (独立集), 或者每条边至少有一个端点被选中
(点覆盖), 在所有通过的集合里按大小以及顶点编号字典序取出一个方案。
顶点多到二十来个就寸步难行, 因为要跑的选法随顶点个数指数增长。

顶点用从零开始的连续整数编号。并列时的取用口径写死: 先比集合大小, 独立集取
最大、点覆盖取最小; 大小相同再比顶点编号序列 (升序后的字典序), 取编号较小
的那一组方案。纯标准库, 无外部依赖。
"""

__all__ = [
    "Erro",
    "Solution",
    "TreeInputError",
    "UnknownVertexError",
    "TreeSolve",
]


class Erro(Exception):
    """本模块所有自定义异常的公共基类, 便于调用方统一捕获。"""


class TreeInputError(Erro):
    """树的构造或查询入参不合法时抛出。"""


class UnknownVertexError(Erro):
    """引用了一个不在树里的顶点时抛出。"""


class Solution:
    """一组解: 选中的顶点集合, 带上集合大小。

    vertices 属性是升序去重的顶点编号元组; size 属性就是它的长度。
    """

    def __init__(self, vertices):
        self.vertices = tuple(sorted(set(vertices)))
        self.size = len(self.vertices)

    def __eq__(self, other):
        return (
            isinstance(other, Solution)
            and self.vertices == other.vertices
        )

    def __repr__(self):
        return "Solution(%r)" % (self.vertices,)


class TreeSolve:
    """在树上枚举选法求最大独立集与最小点覆盖的朴素实现。

    构造时给定顶点个数 n, 顶点编号为零到 n 减一。加边会在两个已知顶点之间
    连一条无向边, 允许重复加同一条边, 但不检查图是否成环 (调用方自己保证是树)。

    - add_edge(u, v): 在 u 与 v 之间连一条边。
    - edges(): 返回去重并按字典序排好的边列表。
    - neighbors(v): 返回 v 的邻居编号升序列表。
    - max_independent_set(): 枚举全部子集求大小最大的独立集。
    - min_vertex_cover(): 枚举全部子集求大小最小的点覆盖。
    - is_independent_set(vertices) / is_vertex_cover(vertices): 判断给定
      顶点集合是否满足相应定义, 中心做法与求解时用的是同一套逐边核对。
    """

    def __init__(self, n):
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise TreeInputError("vertex count must be a non-negative int")
        self._n = n
        self._adj = [[] for _ in range(n)]
        self._edges = set()

    @property
    def n(self):
        """返回顶点个数。"""
        return self._n

    def add_edge(self, u, v):
        """在 u 与 v 之间连一条无向边, 重复加同一条边不报错。"""
        u = self._resolve(u)
        v = self._resolve(v)
        if u == v:
            raise TreeInputError("self loop is not allowed")
        self._edges.add((u, v) if u < v else (v, u))
        self._adj[u].append(v)
        self._adj[v].append(u)

    def edges(self):
        """返回去重并按字典序排好的边列表。"""
        return sorted(self._edges)

    def neighbors(self, v):
        """返回顶点 v 的邻居编号升序列表。"""
        v = self._resolve(v)
        return sorted(set(self._adj[v]))

    def edge_count(self):
        """返回去重后的边数。"""
        return len(self._edges)

    # ------------------------------------------------------------------
    # 求解: 枚举全部选法, 用全部边逐对核对
    # ------------------------------------------------------------------
    def max_independent_set(self):
        """返回大小最大的独立集, 并列时取顶点编号字典序较小的那一组。"""
        best = None
        for mask in range(1 << self._n):
            chosen = [v for v in range(self._n) if mask & (1 << v)]
            if not self.is_independent_set(chosen):
                continue
            best = self._better(best, chosen, maximize=True)
        return Solution(best)

    def min_vertex_cover(self):
        """返回大小最小的点覆盖, 并列时取顶点编号字典序较小的那一组。"""
        best = None
        for mask in range(1 << self._n):
            chosen = [v for v in range(self._n) if mask & (1 << v)]
            if not self.is_vertex_cover(chosen):
                continue
            best = self._better(best, chosen, maximize=False)
        return Solution(best)

    def independent_size(self):
        """返回最大独立集的大小。"""
        return self.max_independent_set().size

    def cover_size(self):
        """返回最小点覆盖的大小。"""
        return self.min_vertex_cover().size

    def is_independent_set(self, vertices):
        """判断给定顶点集合内部有没有边: 集合内任意一条边都不许两端都在集合里。"""
        picked = self._clean(vertices)
        for u, v in self._edges:
            if u in picked and v in picked:
                return False
        return True

    def is_vertex_cover(self, vertices):
        """判断给定顶点集合是不是点覆盖: 每一条边至少有一个端点落在集合里。"""
        picked = self._clean(vertices)
        for u, v in self._edges:
            if u not in picked and v not in picked:
                return False
        return True

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _better(self, best, chosen, maximize):
        """按大小与顶点编号字典序挑出更优的那一组, 返回顶点列表。"""
        if best is None:
            return sorted(chosen)
        cur = sorted(chosen)
        if maximize:
            if len(cur) > len(best) or (len(cur) == len(best) and cur < best):
                return cur
        else:
            if len(cur) < len(best) or (len(cur) == len(best) and cur < best):
                return cur
        return best

    def _clean(self, vertices):
        """把顶点序列去重并校验, 返回升序列表。"""
        if isinstance(vertices, (int, str)) or not hasattr(vertices, "__iter__"):
            raise TreeInputError("vertices must be an iterable of vertex ids")
        seen = set()
        for v in vertices:
            seen.add(self._resolve(v))
        return sorted(seen)

    def _resolve(self, v):
        """把顶点编号校验成合法整数编号。"""
        if isinstance(v, bool) or not isinstance(v, int):
            raise TreeInputError("vertex id must be an int")
        if v < 0 or v >= self._n:
            raise UnknownVertexError("unknown vertex: %r" % (v,))
        return v
