"""dncopt 现状演示。

第一段：在一小组代价序列上跑基线能力，看某一段的和、分成若干组的最小
总代价、最优切割点表，以及枚举切割点的次数。
第二段：预留给改造后的分治路径演示（决策点单调、分治内确定最优决策、
多路逐项对照与规模计数对照），见文末注释，待实现补齐。
"""

from dncopt.core import Optimizer


def demo_baseline():
    print("== 基线：五元素链 ==")
    costs = [1, 2, 3, 4, 5]
    opt = Optimizer(costs)
    print("代价序列 =", opt.costs)
    print("第二到第四段之和 =", opt.seg_sum(2, 4), " 该段代价 =", opt.seg_cost(2, 4))

    print("分成两组最小代价 =", opt.min_cost(2), " 枚举切割点次数 =", opt.naive_op_visits)
    print("分成三组最小代价 =", opt.min_cost(3))
    print("分成两组最优切割点 =", opt.decision_points(2)[2][5])

    print("== 基线：经典四元素 ==")
    four = Optimizer([4, 1, 1, 4])
    print("分成两组最小代价 =", four.min_cost(2))
    print("分成三组最小代价 =", four.min_cost(3))
    print("分成四组最小代价 =", four.min_cost(4))
    print("分成四组最优切割点 =", four.decision_points(4)[4][4])

    print("== 基线：边界 ==")
    empty = Optimizer([])
    print("空序列零组代价 =", empty.min_cost(0))
    print("全零序列两组代价 =", Optimizer([0, 0, 0]).min_cost(2))
    print("单元素一组代价 =", Optimizer([7]).min_cost(1))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
