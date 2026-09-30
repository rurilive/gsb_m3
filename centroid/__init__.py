"""centroid：树的重心与树上路径问题的朴素实现。

现状实现全部走枚举：子树规模对每个结点各跑一遍遍历，重心对每个结点把它删掉
再求最大连通块，两点距离枚举点对后再各自上溯，路径计数枚举全部点对再逐个求
距离。规模一大就退化到平方甚至立方量级，但结果正确、口径固定。
"""

from centroid.core import (
    CentroidError,
    CentroidInputError,
    TreeCentroid,
    UnknownNode,
)

__all__ = ["CentroidError", "CentroidInputError", "TreeCentroid", "UnknownNode"]
