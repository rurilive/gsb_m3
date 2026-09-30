"""NaiveCoinChange 现状演示。

第一段：朴素零钱兑换的最少硬币数、具体选法、可达性与方案个数。
第二段：预留的动态规划与对拍演示位子（见文末注释）。
"""

from coinchange.core import NaiveCoinChange


def main():
    print("=== 朴素零钱兑换（现有能力） ===")
    c = NaiveCoinChange([1, 2, 5], 11)
    print("  规范面值 =", c.coins)
    print("  目标金额 =", c.target)
    print("  最少硬币数 =", c.min_coins())
    print("  具体选法 =", c.selection())
    print("  是否可达 =", c.is_reachable())
    print("  最少枚数的方案个数 =", c.count_min_ways())

    # TODO: 第二段演示（实现后补）

    print("=== 边界约定 ===")
    zero = NaiveCoinChange([1, 2], 0)
    print("  零目标最少硬币数 =", zero.min_coins())
    print("  零目标是否可达 =", zero.is_reachable())
    unreachable = NaiveCoinChange([2, 4], 3)
    print("  无解最少硬币数 =", unreachable.min_coins())
    print("  无解是否可达 =", unreachable.is_reachable())
    print("  无解选法 =", unreachable.selection())


if __name__ == "__main__":
    main()
