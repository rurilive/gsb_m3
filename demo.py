"""treeknapsack 快速演示。

第一段跑改造前的基线能力（朴素枚举的根节点最优、恰好口径最优、每个子树最优，
以及森林判定与朴素枚举次数的规模对照）。
第二段预留给改造后的树形背包与线性序列 DP 演示，待实现补齐。
"""

from treeknapsack.knapsack import TreeKnapsack


def demo_baseline():
    print("== 基线：朴素枚举树形选择 ==")
    p = TreeKnapsack(4, [-1, 0, 0, 1], [2, 3, 1, 4], [3, 4, 5, 6], 5)
    value, chosen = p.brute_best()
    print("根节点最优价值 =", value, " 选中物品 =", chosen)
    print("朴素枚举次数 =", p.brute_visits)

    print("恰好装满容量五的最优 =", p.brute_exact(5))
    print("恰好装满容量四的最优 =", p.brute_exact(4))
    print("每个子树在容量五下的最优 =", p.brute_all_subtrees(5))

    f = TreeKnapsack(4, [-1, 2, -1, 2], [1, 1, 1, 1], [1, 2, 3, 4], 3)
    print("森林根节点 =", f.roots, " 是否森林 =", f.is_forest())

    print("== 基线：规模对照 ==")
    for size in (2, 4, 6):
        parent = [-1] + [0] * (size - 1)
        q = TreeKnapsack(size, parent, [1] * size, [1] * size, size)
        q.brute_best()
        print("节点数 %d：朴素枚举 %d 次" % (size, q.brute_visits))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
