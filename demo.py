"""cdqx 现状演示。

第一段：在一小组三点上跑基线能力，看每个点的偏序计数、总的三维偏序对
个数、按维排序的次序，以及按权值加权的计数，并把两两比较次数打印出来。
第二段：预留给改造后的快速路径演示（CDQ 分治、树状数组维护、多路逐项
对照与规模计数对照），见文末注释，待实现补齐。
"""

from cdqx.core import DominanceCounter


def demo_baseline():
    print("== 基线：三点链 ==")
    points = [(1, 1, 1), (2, 2, 2), (3, 3, 3)]
    dc = DominanceCounter(points)
    print("点集 =", dc.points)

    print("不超过口径逐点计数 =", dc.counts_weak())
    print("两两比较次数 =", dc.last_naive_comparisons)
    print("严格小于口径逐点计数 =", dc.counts_strict())
    print("三维偏序对总数（不超过）=", dc.pairs_weak())
    print("三维偏序对总数（严格）=", dc.pairs_strict())
    print("按第一维排序次序 =", dc.order_by_axis(0))
    print("按第三维排序次序 =", dc.order_by_axis(2))

    print("== 基线：带点权 ==")
    weighted = DominanceCounter(points, [1, 2, 3])
    print("权值 =", weighted.weights)
    print("加权计数（不超过）=", weighted.weighted_counts_weak())
    print("加权计数（严格）=", weighted.weighted_counts_strict())

    print("== 基线：边界 ==")
    empty = DominanceCounter([])
    print("空点集计数 =", empty.counts_weak())
    print("空点集对总数 =", empty.pairs_weak())
    same = DominanceCounter([(2, 2, 2), (2, 2, 2)])
    print("全同点不超过计数 =", same.counts_weak())
    print("全同点严格计数 =", same.counts_strict())


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
