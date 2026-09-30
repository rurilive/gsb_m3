"""flownet: 有向容量网络最大流与最小割的朴素实现。

当前只有两条老路：求最大流时每轮广搜一条增广路再重搜，增广次数与路径长度同阶；
求最小割时枚举边表里所有边子集再走一遍连通性，边一多就指数爆炸。另有判断某组边
是不是割、判断给定容量下有没有割两个能力，走的都是同一套枚举。见 flownet.naive，
分层图多路增广与残量图直接构造割的做法见任务描述。
"""

from flownet.naive import (
    Erro,
    FlowNetwork,
    FlowTools,
    GraphError,
    edge_subset_count,
    feasible_cut,
    is_cut,
    max_flow,
    min_cut,
    min_cut_value,
    reachable,
)

__all__ = [
    "Erro",
    "FlowNetwork",
    "FlowTools",
    "GraphError",
    "edge_subset_count",
    "feasible_cut",
    "is_cut",
    "max_flow",
    "min_cut",
    "min_cut_value",
    "reachable",
]
