"""wgraph: 带非负权图上的最短路。

当前只提供一个最朴素的最短路实现，见 wgraph/shortest.py（WeightedGraph）。
堆优化主路径、朴素口径交叉核对、多源、前驱还原与负权快速失败见任务描述。
"""

from wgraph.shortest import WeightedGraph, UnknownNode, EdgeError

__all__ = ["WeightedGraph", "UnknownNode", "EdgeError"]
