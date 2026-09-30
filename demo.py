"""graycode 现状演示。

第一段：用反复试凑生成格雷码序列、逐个比对定位某个串并枚举子集，打印试凑次数；
第二段：预留的公式法、递归镜像法与逐位翻转法的演示位子（见文末注释）。
"""

from graycode.naive import (
    GrayTools,
    gray_index,
    gray_sequence,
    is_gray_sequence,
    subsets_in_bit_order,
    subsets_in_gray_order,
)


def main():
    print("=== 朴素反复试凑 ===")
    width = 3
    tools = GrayTools(width)
    tools.reset_trial_count()
    seq = tools.gray_sequence()
    print("  位数 %d 的序列共 %d 条" % (width, len(seq)))
    print("  前四条 %s" % (seq[:4],))
    print("  整体合法 %s" % (is_gray_sequence(seq),))
    print("  试凑候选串次数 %d" % tools.trial_count())
    print("  串 101 的位置 %d" % gray_index("101"))

    items = ["a", "b", "c"]
    gray, steps = subsets_in_gray_order(items)
    print("  按位序枚举子集 %s" % (subsets_in_bit_order(items),))
    print("  按格雷序枚举子集 %s" % (gray,))
    print("  每步增删 %s" % (steps,))

    # TODO: 第二段演示（实现后补）
    #
    # 在 graycode 里补出公式法、递归镜像法与逐位翻转法之后，在这里加一段演
    # 示：对同一批位数用三条路各生成一遍序列，与上面试凑的结果逐项对照，并
    # 打印公式法访问次数与朴素试凑次数的差距；再演示格雷码转回二进制的逆运
    # 算、由格雷码值求序号、合法性判定；最后用同一套格雷码顺序枚举集合子集，
    # 与按位序枚举逐项对照并给出每步增删的元素下标；覆盖零位、一位、位数较大、
    # 空集合、单元素、回环首尾、非法序列、含多余元素这些边界，确认各路结论
    # 一致。

    print("  序列末条 %s" % (seq[-1],))


if __name__ == "__main__":
    main()
