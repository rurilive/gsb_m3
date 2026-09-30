"""bit2d 现状演示。

第一段：搭一张小网格，用朴素逐格累加看几次子矩阵求和与点更新的结果，
顺带看看一次子矩阵查询摸过多少格子、重建一次前缀和表要几次；
第二段：预留的二维树状数组改造演示位子（见文末注释）。
"""

from bit2d.grid import NaiveGrid


def main():
    print("=== 朴素逐格累加子矩阵和 ===")
    g = NaiveGrid(3, 4, [
        1, 2, 3, 4,
        5, 6, 7, 8,
        9, 10, 11, 12,
    ])
    print("  网格规模 -> %s" % (g.shape(),))
    print("  整个网格和 -> %d" % g.query(0, 0, 3, 4))
    print("  子矩阵 [0,2)x[0,2) 和 -> %d" % g.query(0, 0, 2, 2))
    print("  子矩阵 [1,3)x[1,4) 和 -> %d" % g.query(1, 1, 3, 4))
    print("  本次摸过格子数 -> %d" % g.last_cost())

    g.update(1, 1, 100)
    print("  把 (1,1) 加 100 后整个网格和 -> %d" % g.query(0, 0, 3, 4))
    g.update(0, 0, -1)
    print("  把 (0,0) 减 1 后子矩阵 [0,2)x[0,2) 和 -> %d" % g.query(0, 0, 2, 2))

    table = g.rebuild_snapshot()
    print("  重建成前缀和表后右下角 -> %d" % table[3][4])
    print("  重建次数 -> %d" % g.rebuild_count())
    print("  空矩形和 -> %d" % g.query(2, 2, 2, 2))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
