"""profiledp 快速演示。

第一段跑改造前的基线能力（逐格全枚举的铺满方案数、带权最优、按行枚举掩码的
独立慢速做法，以及朴素递归展开次数与按行转移次数的规模对照）。
第二段预留给改造后的轮廓线 DP 演示，待实现补齐。
"""

from profiledp.profile import ProfileDp


def demo_baseline():
    print("== 基线：逐格全枚举铺放 ==")
    p = ProfileDp(3, 4)
    print("三行四列铺满方案数 =", p.brute_count(), " 探测次数 =", p.brute_visit_count)
    print("最小规范形 =", p.brute_canonical())

    q = ProfileDp(3, 4, names=("domino_h", "domino_v", "L_a", "L_b"))
    print("三行四列含 L 形方案数 =", q.brute_count())

    w = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
    value, layout = q.brute_best(w)
    print("带权最优权重和 =", value, " 布局 =", layout)

    print("== 基线：独立按行枚举掩码 ==")
    print("三行四列按行枚举方案数 =", ProfileDp(3, 4).independent_rows(),
          " 转移次数 =", _row_visits(3, 4))

    print("== 基线：规模对照 ==")
    for size in (2, 3, 4):
        naive = ProfileDp(size, size)
        naive.brute_count()
        rows = ProfileDp(size, size)
        rows.independent_rows()
        print("%d 乘 %d：朴素探测 %d 次，按行转移 %d 次"
              % (size, size, naive.brute_visit_count, rows.row_visit_count))


def _row_visits(rows, cols):
    p = ProfileDp(rows, cols)
    p.independent_rows()
    return p.row_visit_count


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
