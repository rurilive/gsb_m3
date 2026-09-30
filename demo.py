"""areaunion 快速演示。

第一段跑改造前的基线能力（坐标离散化后逐小格逐矩形判定的并集面积、周长、
至少 k 次与恰好 k 次面积，以及两条独立的逐格慢速做法与判定次数的规模对照）。
第二段预留给改造后的扫描线加线段树路径演示，待实现补齐。
"""

from areaunion.area import RectSet


def demo_baseline():
    print("== 基线：离散化逐格判定 ==")
    s = RectSet([(0, 0, 2, 2), (1, 1, 3, 3), (10, 10, 11, 11), (10, 10, 10, 10)])
    print("小格数 =", s.cell_count())
    print("并集面积 =", s.union_area())
    print("并集周长 =", s.perimeter())

    print("== 基线：覆盖次数面积 ==")
    print("至少 1 次面积 =", s.area_at_least(1))
    print("至少 2 次面积 =", s.area_at_least(2))
    print("恰好 1 次面积 =", s.area_exactly(1))
    print("最大覆盖次数 =", s.max_overlap())

    print("== 基线：逐点判定 ==")
    print("点 (1, 1) 被覆盖下标 =", s.covers_point(1, 1))
    print("点 (1, 1) 覆盖数 =", s.coverage_count_at(1, 1))

    print("== 基线：独立逐格慢速做法 ==")
    print("独立并集面积 =", s.independent_brute_area())
    print("独立至少 2 次面积 =", s.independent_brute_area_at_least(2))
    print("独立周长 =", s.independent_brute_perimeter())

    print("== 基线：规模对照 ==")
    for n in (4, 8, 12):
        big = RectSet([(i, i, i + 3, i + 3) for i in range(n)])
        big.union_area()
        print("%d 个矩形：判定 %d 次，线段树结点访问 %d 次"
              % (n, big.judge_count(), big.node_access_count()))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
