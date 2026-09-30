"""assignmatch 现状演示。

第一段：用枚举全部置换这一条朴素路演示求最小代价指派、求最大收益指派、求某个
指派的总代价与是否最优、求最大匹配下的最优指派，并打印置换枚举计数；
第二段：预留的匈牙利增广、最小费用最大流与规模对照演示位子（见文末注释）。
"""

from assignmatch.naive import (
    AssignTools,
    INF,
    assignment_cost,
    best_partial_assignment,
    is_optimal,
    max_profit_assignment,
    min_cost_assignment,
    permutation_count,
)


def main():
    print("=== 朴素枚举置换 ===")
    cost = [
        [4, 1, 3],
        [2, 0, 5],
        [3, 2, 2],
    ]
    low = min_cost_assignment(cost)
    print("  最小总代价 %d，方案 %s" % (low["cost"], low["assignment"]))
    high = max_profit_assignment(cost)
    print("  最大总收益 %d，方案 %s" % (high["cost"], high["assignment"]))
    print("  方案 %s 的总代价 %d" % ([1, 0, 2], assignment_cost(cost, [1, 0, 2])))
    print("  方案 %s 是不是最小 %s" % ([1, 0, 2], is_optimal(cost, [1, 0, 2])))
    print("  三阶置换总数 %d" % permutation_count(3))

    print("  工人生少任务多的最大匹配最优 %s" % (
        best_partial_assignment([[9, 2, 7], [6, 4, 3]]),))
    print("  含不可用格子的最大匹配最优 %s" % (
        best_partial_assignment([[1, None, 4], [None, 2, 8], [3, 9, None]]),))
    print("  无穷大当作不可用 %s" % (
        best_partial_assignment([[1, INF], [2, 3]]),))

    tools = AssignTools(cost)
    tools.reset_permutation_count()
    tools.min_cost_assignment()
    tools.max_profit_assignment()
    print("  两次枚举累计候选数 %d" % tools.permutation_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 assignmatch 里补出匈牙利增广路与最小费用最大流两条独立做法之后，在这里
    # 加一段演示：对同一批代价矩阵用两条路各求一遍最小代价指派与最优方案，逐项对
    # 照结果是否一致，并与枚举置换路在小规模上三方对齐；再演示最大收益指派、最大
    # 匹配下的最优指派、给定方案求总代价与判断是否最优这几个能力，与各自朴素口径
    # 逐项比对；并排打印匈牙利增广次数与朴素枚举置换次数，覆盖空矩阵、单工人单任
    # 务、方阵、非方阵、负代价、全同代价、不可用组合、零代价这些边界。


if __name__ == "__main__":
    main()
