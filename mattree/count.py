"""mattree: 无向图生成树计数的朴素实现。

当前只有一份暴力实现：把全部边子集枚举一遍，逐个子集判定边数是否等于
点数减一、以及是否把全部节点连成一片，两个条件都满足才计一棵。结果正确，
代价却随边的条数按二的边数次方增长，图稍大就跑不动。

按矩阵树定理构造基尔霍夫矩阵、划去一行一列后在高斯消元下求模某大素数的
行列式，以及独立印证与边界覆盖，见任务描述。
"""

from itertools import combinations


class Erro(Exception):
    """mattree 全部异常的基类。"""


class IllegalArgument(Erro):
    """节点数或边表本身不合法。"""


class UnknownNode(Erro):
    """边引用了不存在的节点。"""


def normalize_edges(edges):
    """把边表规范成有序的端点对列表，保留重边与自环的原有顺序。"""
    out = []
    for e in edges:
        if isinstance(e, (str, bytes)) or not isinstance(e, (tuple, list)):
            raise IllegalArgument("edge must be a pair")
        if len(e) != 2:
            raise IllegalArgument("edge must have exactly two endpoints")
        u, v = e
        for x in (u, v):
            if isinstance(x, bool) or not isinstance(x, int):
                raise IllegalArgument("edge endpoint must be an int")
        out.append((u, v))
    return out


def check_graph(n, edges):
    """校验节点数与边表，返回规范后的边列表；不合法就就近报错。"""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise IllegalArgument("node count must be a positive int")
    es = normalize_edges(edges)
    for u, v in es:
        if not (0 <= u < n) or not (0 <= v < n):
            raise UnknownNode("edge endpoint out of range")
    return es


def is_connected(n, edges):
    """并查集判定 n 个节点是否连成一片，自环不影响连通性。"""
    es = check_graph(n, edges)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in es:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    root = find(0)
    return all(find(i) == root for i in range(n))


def degrees(n, edges):
    """度数序列，自环给该端点计两次，重边各计一次。"""
    es = check_graph(n, edges)
    deg = [0] * n
    for u, v in es:
        deg[u] += 1
        deg[v] += 1
    return deg


def is_spanning_tree(n, edges):
    """边数恰为点数减一，并且把全部节点连成一片，才算一棵生成树。"""
    es = check_graph(n, edges)
    if len(es) != n - 1:
        return False
    return is_connected(n, es)


def count_spanning_trees(n, edges):
    """暴力枚举全部边子集，逐个判定是否为生成树，统计生成树个数。"""
    es = check_graph(n, edges)
    m = len(es)
    total = 0
    for mask in range(1 << m):
        chosen = [es[i] for i in range(m) if (mask >> i) & 1]
        if len(chosen) != n - 1:
            continue
        if is_connected(n, chosen):
            total += 1
    return total


def enumerate_trees(n, edges):
    """把全部生成树按边子集列出来，每个子集按输入边序排列，便于对照。"""
    es = check_graph(n, edges)
    m = len(es)
    found = []
    for mask in range(1 << m):
        chosen = [es[i] for i in range(m) if (mask >> i) & 1]
        if len(chosen) != n - 1:
            continue
        if is_connected(n, chosen):
            found.append(chosen)
    return found
