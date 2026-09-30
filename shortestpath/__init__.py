"""shortestpath：带非负权图的单源最短路工具包的朴素基线。

导出 NaiveGraph 类与全部异常类型。基线每轮在未确定结点里线性扫描找出
距离最小者，再逐边松驰其邻居，找最小这一步整体线性，单次求解随结点数
平方增长。
"""

from .dijkstra import (
    NaiveGraph,
    NegativeWeightError,
    NodeNotFoundError,
    ShortestPathError,
    UnreachableNodeError,
)

__all__ = [
    "NaiveGraph",
    "NegativeWeightError",
    "NodeNotFoundError",
    "ShortestPathError",
    "UnreachableNodeError",
]
