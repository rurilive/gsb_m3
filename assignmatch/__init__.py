"""assignmatch: 指派问题工具的朴素实现。

当前只有一条路：给定代价矩阵求最小总代价的完美指派、求最大收益指派、判断某个
指派是不是最优、求最大匹配下的最优指派，全靠枚举全部置换再逐个算总代价。见
assignmatch.naive，匈牙利增广与最小费用最大流这类做法见任务描述。
"""

from assignmatch.naive import (
    AssignTools,
    Erro,
    INF,
    MatrixError,
    assignment_cost,
    best_partial_assignment,
    enumerate_permutations,
    is_optimal,
    max_profit_assignment,
    min_cost_assignment,
    permutation_count,
)

__all__ = [
    "AssignTools",
    "Erro",
    "INF",
    "MatrixError",
    "assignment_cost",
    "best_partial_assignment",
    "enumerate_permutations",
    "is_optimal",
    "max_profit_assignment",
    "min_cost_assignment",
    "permutation_count",
]
