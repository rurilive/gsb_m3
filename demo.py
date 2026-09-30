"""ternsearch 现状演示。

第一段：拿一个开口向上的二次函数与一座倒扣的山包，用枚举定义域的方式
求最小值、最大值、峰值位置与凸函数最值，并打印枚举的求值次数，看看定义域
一大要算多少下；
第二段：预留的三分法与两条印证路、单峰判定的演示位子（见文末注释）。
"""

from ternsearch.extremum import DiscreteSequence, PeakFinder


def parabola(x):
    return (x - 5) * (x - 5)


def mountain(x):
    return -(x - 3) * (x - 3) + 10


def main():
    print("=== 朴素枚举求极值 ===")
    f = PeakFinder()
    print("  parabola 定义域 [-10, 10]")
    print("    最小值 %s" % (f.minimize(parabola, -10, 10),))
    print("    最大值 %s" % (f.maximize(parabola, -10, 10),))
    print("  mountain 定义域 [-10, 10]")
    print("    峰值位置 %s" % f.peak_position(mountain, -10, 10))
    print("    最大值 %s" % (f.maximize(mountain, -10, 10),))
    print("  二次函数 x*x - 10*x + 30 在 [8, 100] 上")
    print("    最小值 %s" % (f.convex_minimum(1, -10, 30, 8, 100),))
    seq = DiscreteSequence([1, 3, 5, 5, 4, 2])
    print("  离散序列 %s" % (seq.values(),))
    print("    是否单峰 %s" % seq.is_unimodal())
    print("    峰值位置 %s" % f.sequence_peak(seq))
    print("  枚举定义域 [0, 100000] 求最小值的求值次数")
    print("    %d" % f.eval_count(parabola, 0, 100000))

    # TODO: 第二段演示（实现后补）
    #   三分法把这四次能力（整数或浮点单峰函数的最小值、最大值、峰值位置、
    #   离散单峰序列的峰值位置）从线性枚举降到对数之后，在这里对同一批函数和
    #   序列各跑一遍三分法，打印极值位置与极值，确认与上面枚举的结果逐项一致；
    #   再用导数或差分加二分、以及斐波那契搜索或黄金分割比各求一遍，打印三方
    #   与枚举的结果互相对照；最后打印三分法的求值次数，和枚举的十万次比一比。


if __name__ == "__main__":
    main()
