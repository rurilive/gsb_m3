"""mattree: 无向图生成树计数工具。

当前只有暴力实现，见 mattree/count.py。生成树计数把所有边子集枚举一遍，
逐个子集判定边数是否为点数减一、是否把全部节点连成一片，两个条件都满足
才计一棵，代价随边数次方增长。度数序列、连通判定与生成树判定也都当场现算。

按矩阵树定理构造基尔霍夫矩阵、划去一行一列后用高斯消元求模大素数的行列式，
以及普吕弗序列或凯莱公式的独立印证、边界与确定性，见任务描述。
"""

from mattree.count import (
    Erro,
    IllegalArgument,
    UnknownNode,
    check_graph,
    count_spanning_trees,
    degrees,
    enumerate_trees,
    is_connected,
    is_spanning_tree,
    normalize_edges,
)

__all__ = [
    "Erro",
    "IllegalArgument",
    "UnknownNode",
    "check_graph",
    "count_spanning_trees",
    "degrees",
    "enumerate_trees",
    "is_connected",
    "is_spanning_tree",
    "normalize_edges",
]
