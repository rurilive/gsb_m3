"""sortx 现状演示。

第一段：用朴素实现做一轮整数排序、非负整数排序、定点数排序、按自定义键
排序与取值统计，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from sortx.sortkit import (
    compare_with_builtin,
    count_max,
    count_min,
    describe_family,
    fixed_sort,
    integer_sort,
    key_sort,
    nonnegative_sort,
    sort_and_assert_stable,
)


def main():
    print("=== 朴素排序：整数与负数 ===")
    data = [3, -1, 2, 0, -5, 2]
    print(f"  输入           -> {data}")
    print(f"  整数排序       -> {integer_sort(data)}")
    print(f"  稳定判据结果   -> {sort_and_assert_stable(data)}")

    print("=== 朴素排序：与内置全排序比对 ===")
    result, same = compare_with_builtin(data)
    print(f"  本包结果       -> {result}")
    print(f"  与内置一致     -> {same}")

    print("=== 朴素排序：非负整数 ===")
    print(f"  输入           -> {[5, 0, 3, 3, 1]}")
    print(f"  非负排序       -> {nonnegative_sort([5, 0, 3, 3, 1])}")

    print("=== 朴素排序：带固定小数位的定点数 ===")
    print(f"  两位小数输入   -> {[2.5, 1.25, 2.5, -1.5]}")
    print(f"  定点排序       -> {fixed_sort([2.5, 1.25, 2.5, -1.5], 2)}")

    print("=== 朴素排序：按自定义键 ===")
    words = ["bb", "a", "ccc"]
    print(f"  输入           -> {words}")
    print(f"  按键长排序     -> {key_sort(words, len)}")

    print("=== 朴素统计：取值上下限 ===")
    print(f"  最大值         -> {count_max(data)}")
    print(f"  最小值         -> {count_min(data)}")

    print("=== 计划中的成员 ===")
    print(f"  {describe_family()}")

    # TODO: 第二段演示（实现后补）
    # 说明：线性时间排序族改造完成后，在这里补一段演示——对同一批固定数据
    # 分别用计数排序、基数排序与桶排序跑一遍，逐项断言结果与上面这条内置
    # 全排序路径完全一致，并打印比较次数或者分配计数，量出线性排序不做元素
    # 间比较这一事实，让新路径能直接跑通并正常退出。


if __name__ == "__main__":
    main()
