"""digitx 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from digitx.count import BruteDigits


def baseline_demo():
    bd = BruteDigits()
    print("含数字 1 的整数个数（一到 100）:", bd.count_with_digit(100, 1))
    print("含数字 0 的整数个数（一到 1000）:", bd.count_with_digit(1000, 0))
    print("各位数字之和（一到 100）:", bd.sum_of_digits(100))
    print("不大于 30 的整数个数（一到 50）:", bd.count_less_than(50, 30))
    print("能被 7 整除的整数个数（一到 1000）:", bd.count_divisible(1000, 7))


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：数位动态规划计数 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
