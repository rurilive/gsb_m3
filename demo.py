"""dlx 现状演示。

第一段：朴素实现——把矩阵当成二维表，按行号从小到大回溯枚举，逐列线性检查
冲突，在这条路上求一个解、枚举全部解、求行数最少的解、判给定行集合是不是
精确覆盖，并打印探测状态规模。
第二段：预留的舞蹈链与对拍演示位子（见文末注释）。
"""

from dlx import (
    column_coverage,
    conflict_columns,
    is_exact_cover,
    minimum_solution,
    search_steps,
    solution_count,
    solve,
    solve_all,
)

# 四行四列样本：第一列只在第零行出现，故第零行必选，共有两个解。
SAMPLE = [
    [1, 0, 1, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 1, 1, 0],
]


def main():
    print("=== 朴素二维表回溯枚举 ===")
    print("  样本矩阵 %s" % SAMPLE)
    print("  一个解 -> %s" % solve(SAMPLE))
    print("  全部解 -> %s" % solve_all(SAMPLE))
    print("  解的个数 -> %d" % solution_count(SAMPLE))
    print("  行数最少的解 -> %s" % minimum_solution(SAMPLE))

    good = [0, 1, 2]
    print("  行集合 %s 是不是精确覆盖 -> %s" % (good, is_exact_cover(SAMPLE, good)))
    print("  行集合 [0, 1] 是不是精确覆盖 -> %s" % is_exact_cover(SAMPLE, [0, 1]))
    print("  第零行覆盖的列 -> %s" % column_coverage(SAMPLE, 0))
    print("  行 1 与行 3 的冲突列 -> %s" % conflict_columns(SAMPLE, [1, 3]))
    print("  探测状态规模 -> %d" % search_steps(SAMPLE))

    print("=== 无解与边界 ===")
    print("  列重复的小矩阵 -> %s" % solve([[1, 0], [1, 0]]))
    print("  空矩阵求解 -> %s" % solve([]))
    print("  单行单列 -> %s" % solve([[1]]))
    print("  全零矩阵 -> %s" % solve([[0]]))

    # TODO: 第二段演示（实现后补）
    # 在 dlx 里补出按列头双向循环十字链表组织的舞蹈链，以及一条独立可读的朴素
    # 回溯路之后，在这里加一段演示：对同一批矩阵用舞蹈链路与朴素路各求一遍一个
    # 解、全部解、行数最少的解与解的个数，逐项对照结果是否一致；再演示舞蹈链路
    # 对空矩阵、单行单列、无解、唯一解、多解这些边界的结论；并排打印舞蹈链路的
    # 覆盖剔除次数与朴素路的探测状态规模，确认同一批输入重复跑结果不变。


if __name__ == "__main__":
    main()
