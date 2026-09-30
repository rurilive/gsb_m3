"""unionfind：并查集与动态连通性的朴素实现。

现状用根到成员列表的字典维护集合，合并时逐元素搬移，查询时逐元素线性扫描，
带权偏移逐元素重算，回滚靠整份状态深拷贝。口径直白、结果确定，但合并与查询一多
就退化到平方量级。异常统一从 UnionFindError 派生。
"""

from unionfind.core import (
    IllegalRollback,
    NotConnected,
    UnionFind,
    UnionFindError,
    UnionFindInputError,
    UnknownNode,
)

__all__ = [
    "IllegalRollback",
    "NotConnected",
    "UnionFind",
    "UnionFindError",
    "UnionFindInputError",
    "UnknownNode",
]
