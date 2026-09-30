"""NaiveEnumerator 现状演示。

第一段：朴素组合与排列枚举的计数、全部结果、第几个与名次。
第二段：预留的迭代生成与阶乘进制解析演示位子（见文末注释）。
"""

from combperm.enumerate import NaiveEnumerator


def main():
    print("=== 朴素组合排列枚举（现有能力） ===")
    e = NaiveEnumerator(4)
    print("  规模 =", e.size())
    print("  组合数 取2 =", e.combinations_count(2))
    print("  排列数 取2 =", e.permutations_count(2))
    print("  全部组合 取2 =", e.all_combinations(2))
    print("  全部排列 取3 =", e.all_permutations(3))
    print("  第0个排列 =", e.nth(4, 0, "perm"))
    print("  第5个排列 =", e.nth(4, 5, "perm"))
    print("  排列 (0, 3, 2, 1) 的名次 =", e.rank((0, 3, 2, 1), "perm"))
    print("  组合 (1, 3) 的名次 =", e.rank((1, 3), "comb"))

    # TODO: 第二段演示（实现后补）

    print("=== 边界约定 ===")
    empty = NaiveEnumerator(0)
    print("  规模0 组合数 取0 =", empty.combinations_count(0))
    print("  规模0 排列数 取0 =", empty.permutations_count(0))


if __name__ == "__main__":
    main()
