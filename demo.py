"""bitmaskx 快速演示。

第一段跑改造前的基线能力（全排列枚举的哈密顿路径与回路、组合枚举的集合覆盖、
递归枚举的划分）。
第二段预留给改造后的按掩码从小到大递推的高效路径演示，待实现补齐。
"""

from bitmaskx.bitmask import MaskDp


def demo_baseline():
    print("== 基线：朴素枚举路径 ==")
    k = MaskDp(4)
    dist = [
        [0, 3, 7, 5],
        [3, 0, 2, 6],
        [7, 2, 0, 4],
        [5, 6, 4, 0],
    ]
    cost, path = k.shortest_hamiltonian(dist, 0)
    print("最短哈密顿路径代价 =", cost, " 路径 =", path, " 排列枚举次数 =", k.perm_visits)

    cycle_cost, cycle_path = k.shortest_cycle(dist, 0)
    print("最短哈密顿回路代价 =", cycle_cost, " 回路 =", cycle_path)

    subsets = [0b0011, 0b0100, 0b1000]
    cnt, chosen = k.min_cover(0b1111, subsets)
    print("集合覆盖最少个数 =", cnt, " 方案 =", chosen, " 组合枚举次数 =", k.cover_visits)

    g = MaskDp(3)
    related = [
        [1, 1, 0],
        [1, 1, 1],
        [0, 1, 1],
    ]
    groups, part = g.min_groups(related)
    print("最优划分组数 =", groups, " 划分 =", part, " 划分枚举次数 =", g.partition_visits)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
