"""subsetconv 现状演示。

第一段：对长度 4 的两个数组，逐种跑一遍朴素卷积。
第二段：预留的快速变换演示位子（见文末 TODO 注释）。
"""

from subsetconv import SetFunction


def main():
    a = [1, 2, 3, 4]
    b = [5, 6, 7, 8]
    fa = SetFunction(a)
    fb = SetFunction(b)

    print("=== 朴素逐对累加卷积（现有能力） ===")
    print("  a            = %s" % (a,))
    print("  b            = %s" % (b,))
    print("  or_convolve  = %s" % (fa.or_convolve(fb).as_list(),))
    print("  and_convolve = %s" % (fa.and_convolve(fb).as_list(),))
    print("  xor_convolve = %s" % (fa.xor_convolve(fb).as_list(),))
    print("  subset_conv  = %s" % (fa.subset_convolve(fb).as_list(),))
    print("  下标对数      = %s" % (fa.pair_count(),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
