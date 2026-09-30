"""boruvka: 无向带权图的朴素最小生成森林工具。

当前只有一份改造前的朴素实现：每一轮，对每个连通分量把整张边表从头到尾
线性扫一遍，挑出连接它到别的分量的最便宜的一条边，挑中的边加进来，反复
若干轮直到再也加不动。小图上结果正确，规模一大代价就高。

按博鲁夫卡算法改造（每轮每个分量各选一条连出去的最轻边、并查集合并，
分量数至少减半、轮数为对数级），以及克鲁斯卡尔独立路径、边界与确定性，
见任务描述。
"""


class Erro(Exception):
    """本库全部异常的基类。"""


class IllegalArgument(Erro):
    """参数不合格，例如节点数非正、权重为负、边不是一条三元组。"""


class UnknownNode(Erro):
    """边的端点落在节点编号范围之外。"""


def check_graph(n, edges):
    """校验节点数 n 与边表 edges，非法就在此处报错。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise IllegalArgument("节点数必须是整数")
    if n < 1:
        raise IllegalArgument("节点数必须为正")
    if not isinstance(edges, (list, tuple)):
        raise IllegalArgument("边表必须是序列")
    for item in edges:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise IllegalArgument("每条边必须是端点、端点、权重三个分量")
        u, v, w = item
        for node in (u, v):
            if isinstance(node, bool) or not isinstance(node, int):
                raise IllegalArgument("端点必须是整数")
            if node < 0 or node >= n:
                raise UnknownNode("端点超出节点编号范围")
        if isinstance(w, bool) or not isinstance(w, int):
            raise IllegalArgument("权重必须是整数")
        if w < 0:
            raise IllegalArgument("权重不能为负")


def normalize_edges(n, edges):
    """校验后把边表规范成三元组列表，保持给出的先后次序。"""
    check_graph(n, edges)
    return [(u, v, w) for (u, v, w) in edges]


def _components(n, edges):
    """朴素地给每个节点打连通分量标号，最小的成员编号即分量号。"""
    label = list(range(n))
    changed = True
    while changed:
        changed = False
        for (u, v, _w) in edges:
            a, b = label[u], label[v]
            if a != b:
                lo = a if a < b else b
                for k in range(n):
                    if label[k] == a or label[k] == b:
                        label[k] = lo
                changed = True
    return label


def is_connected(n, edges):
    """全图是否连成一片，单点图算连通，空边表的多点图不连通。"""
    es = normalize_edges(n, edges)
    return len(set(_components(n, es))) == 1


def mst_edges(n, edges):
    """最小生成森林所选边的下标集合，指向输入边表的下标，按权重再按下标升序。"""
    es = normalize_edges(n, edges)
    selected = []
    while True:
        label = _components(n, [es[i] for i in selected])
        groups = {}
        for v in range(n):
            groups.setdefault(label[v], []).append(v)
        picked = []
        for root in sorted(groups):
            best = None
            for i in range(len(es)):
                u, v, w = es[i]
                if u == v:
                    continue
                if label[u] == label[v]:
                    continue
                if label[u] != root and label[v] != root:
                    continue
                if best is None or (w, i) < (best[0], best[1]):
                    best = (w, i)
            if best is not None:
                picked.append(best[1])
        added = False
        for i in picked:
            if i not in selected:
                selected.append(i)
                added = True
        if not added:
            break
    selected.sort(key=lambda i: (es[i][2], i))
    return selected


def mst_weight(n, edges):
    """最小生成森林的总权值。"""
    es = normalize_edges(n, edges)
    return sum(es[i][2] for i in mst_edges(n, es))


def components(n, edges):
    """各节点所属连通分量，返回一种确定的分量划分，按最小成员编号升序排好。"""
    es = normalize_edges(n, edges)
    label = _components(n, es)
    groups = {}
    for v in range(n):
        groups.setdefault(label[v], []).append(v)
    return [groups[key] for key in sorted(groups)]
