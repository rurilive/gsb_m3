"""digitcount 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from digitcount.counter import NaiveDigitCounter


def baseline_demo():
    nc = NaiveDigitCounter()
    print("各位数字之和对 9 取余为零的整数个数（一到 100）:", nc.count_sum_mod(1, 100, 9, 0))
    print("含数字 1 的整数个数（一到 100）:", nc.count_contains(1, 100, 1))
    print("含数字 0 的整数个数（一到 100）:", nc.count_contains(1, 100, 0))
    print("数位不下降的整数个数（一到 1000）:", nc.count_monotonic(1, 1000))
    print("回文整数个数（一到 1000）:", nc.count_palindrome(1, 1000))


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：数位动态规划区间计数 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
