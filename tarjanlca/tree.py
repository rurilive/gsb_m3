"""森林上的朴素最近公共祖先：每个询问都重标一次端点到根的路径。

每次询问两点最近公共祖先时，先把其中一点到根的整条路径逐级上溯、
全部标记出来，再让另一点往根上走，第一个遇见的被标记点即为答案。
标记在每个询问里重建一次，规模一大就按询问数乘深度增长；结果正确。
"""


class Erro(Exception):
    """本模块所有异常的基类。"""


class IllegalArgument(Erro):
    """入参形态不合法，例如父指针表不是字典或为空。"""


class UnknownNode(Erro):
    """查询里出现了不在本森林中的结点编号。"""


class InvalidForest(Erro):
    """结构不合法，例如父结点不存在或上溯出现环。"""


class Tree(object):
    """一片森林，用父指针表示，允许有多个连通块。

    parents 为字典，键是每一个结点编号，值是它的父结点编号；
    连通块的根结点父指针记作 None。构造时会把结构校验一遍。
    """

    def __init__(self, parents):
        if not isinstance(parents, dict):
            raise IllegalArgument("parents 必须是字典")
        if not parents:
            raise IllegalArgument("森林至少需要一个结点")
        self._parents = dict(parents)
        self._validate()

    def _validate(self):
        for node in self._parents:
            parent = self._parents[node]
            if parent is not None and parent not in self._parents:
                raise InvalidForest("父结点 %r 不在森林中" % (parent,))
        for node in self._parents:
            seen = set()
            cur = node
            while cur is not None:
                if cur in seen:
                    raise InvalidForest("从结点 %r 上溯出现环" % (node,))
                seen.add(cur)
                cur = self._parents[cur]

    def nodes(self):
        """返回全部结点编号的升序列表。"""
        return sorted(self._parents.keys())

    def roots(self):
        """返回全部连通块根结点的升序列表。"""
        return sorted(n for n in self._parents if self._parents[n] is None)

    def _require(self, node):
        if node not in self._parents:
            raise UnknownNode("结点 %r 不在森林中" % (node,))

    def path_to_root(self, node):
        """从 node 一路沿父指针走到所在连通块的根，返回含两端的列表。"""
        self._require(node)
        out = []
        cur = node
        while cur is not None:
            out.append(cur)
            cur = self._parents[cur]
        return out

    def depth(self, node):
        """结点到所在连通块根的距离，根为 0；靠逐级上溯数步数。"""
        return len(self.path_to_root(node)) - 1

    def lca(self, u, v):
        """最近公共祖先：先标记一端到根的整条路径，再让另一端上溯找第一个命中点。

        两个端点落在不同连通块时返回 None。每个询问都重新标记一次。
        """
        self._require(u)
        self._require(v)
        marked = set()
        cur = u
        while cur is not None:
            marked.add(cur)
            cur = self._parents[cur]
        cur = v
        while cur is not None:
            if cur in marked:
                return cur
            cur = self._parents[cur]
        return None

    def lca_all(self, pairs):
        """对一批点对逐个调用朴素最近公共祖先，返回结果列表。"""
        return [self.lca(u, v) for (u, v) in pairs]
