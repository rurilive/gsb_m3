"""slopeopt 快速演示。

第一段跑改造前的基线能力（朴素两两枚举求最优）。
第二段预留给改造后的高效路径演示（单调队列凸包与李超树），待实现补齐。
"""

from slopeopt.core import OptKit, Program


def demo_baseline():
    print("== 基线：朴素两两枚举路径 ==")
    kit = OptKit(Program(slope=3, intercept=5, k=1))

    weights = [4, -3, 7, 2, -5]
    res = kit.optimize(weights)
    print("权值序列 =", weights)
    print("dp 序列  =", res["dp"])
    print("最优决策 =", res["best"])
    print("比较次数 =", res["steps"], " 候选转移 =", kit.transitions)

    step2 = OptKit(Program(slope=-2, intercept=4, k=2))
    res2 = step2.optimize([10, 6, 1, 8, 3, 5])
    print("步长为二 dp 序列 =", res2["dp"])

    small = OptKit(Program(slope=0, intercept=7, k=1))
    print("截距全同 dp 序列 =", small.optimize([5, 0, 5, 10])["dp"])


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
