"""spanlab 现状演示。

第一段：朴素双向扫描——每个位置向左向右各看一遍，求左右第一个更大或更小元素，
并据此给出柱状图最大矩形、子数组最小值之和与作为最小值出现的子数组个数。
第二段：预留的单调栈与逐项对照演示的位子（见文末注释）。
"""

from spanlab import (
    bounds_greater,
    bounds_smaller,
    count_brute_scans,
    count_subarrays_as_min,
    largest_rectangle,
    sum_of_subarray_mins,
)


def main():
    data = [3, 1, 4, 1, 5, 9, 2, 6]

    print("=== 朴素双向扫描：左右第一个更大与更小 ===")
    greater_left, greater_right = bounds_greater(data)
    smaller_left, smaller_right = bounds_smaller(data)
    print(f"  数据               {data}")
    print(f"  左侧第一个更大下标 {greater_left}")
    print(f"  右侧第一个更大下标 {greater_right}")
    print(f"  左侧第一个更小下标 {smaller_left}")
    print(f"  右侧第一个更小下标 {smaller_right}")

    print("=== 朴素派生量 ===")
    print(f"  柱状图最大矩形面积 {largest_rectangle(data)}")
    print(f"  子数组最小值之和   {sum_of_subarray_mins(data)}")
    print(f"  每个元素作为最小值的子数组个数 {count_subarrays_as_min(data)}")
    print(f"  本轮双向扫描比较次数 {count_brute_scans(data)}")

    # TODO: 第二段演示（实现后补）
    # 补上单调栈一次遍历求四类左右边界、柱状图最大矩形、子数组最小与最大之和、
    # 每个元素作为最小值出现的子数组计数，并与本条朴素路径对同一批序列逐项对照；
    # 再打印双向扫描次数与栈总入出栈次数的差距，以及空序列、单元素、全相等、
    # 严格递增、严格递减、含重复值等边界上的结果。


if __name__ == "__main__":
    main()
