"""permparity 现状演示。

第一段：用朴素口径回答一个小排列的逆序数、奇偶性与置换分解问题，看两两比较
次数随元素个数按平方量级增长，并演示最少交换次数与置换复合；
第二段：预留的归并、树状数组与循环符号演示位子，见文末注释。
"""

from permparity import (
    validate_perm,
    inversion_count,
    parity,
    is_even,
    cycle_decomposition,
    min_swaps,
    cycle_type,
    parity_by_cycles,
    compose,
    compose_parity,
    can_swap,
    min_swaps_between,
)


def main():
    print("=== 朴素两两比较 ===")
    perm = [3, 1, 4, 0, 2]
    print("  排列 %s" % (perm,))
    print("  校验后 %s" % (validate_perm(perm),))
    print("  逆序数与比较次数 %s" % (inversion_count(perm),))
    print("  奇偶性 %s，是否偶排列 %r" % (parity(perm), is_even(perm)))
    print("  循环分解 %s" % (cycle_decomposition(perm),))
    print("  循环长度 %s" % (cycle_type(perm),))
    print("  最少交换次数 %d" % (min_swaps(perm),))
    print("  循环口径奇偶 %s" % (parity_by_cycles(perm),))

    print("  完全逆序 %s" % (inversion_count([4, 3, 2, 1, 0]),))
    print("  单位排列 %s" % (inversion_count([0, 1, 2, 3, 4]),))

    print("  两两比较随元素个数增长：")
    for n in (4, 8, 16, 32):
        _, comparisons = inversion_count(list(range(n)))
        print("    元素 %2d 个，比较 %5d 次" % (n, comparisons))

    print("  置换复合 %s" % (compose([1, 0, 2], [0, 2, 1]),))
    print("  复合后的奇偶 %s" % (compose_parity([1, 0, 2], [0, 2, 1]),))
    print("  能否互化 %r" % (can_swap([2, 0, 1], [0, 1, 2]),))
    print("  互相转化的最少交换 %d" % (min_swaps_between([2, 0, 1], [0, 1, 2]),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
