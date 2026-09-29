"""NaiveStats 现状演示。

第一段：朴素流式统计的推入、均值、中位数、最值与排序副本。
第二段：预留的在线中位数与分位数演示位子（见文末注释）。
"""

from statlib.running import NaiveStats


def main():
    print("=== 朴素流式统计（现有能力） ===")
    s = NaiveStats()
    for x in (12.0, 4.0, 30.0, 18.0, 7.0):
        s.push(x)
    print("  个数 =", s.count())
    print("  均值 =", s.mean())
    print("  中位数 =", s.median())
    print("  最小值 =", s.min())
    print("  最大值 =", s.max())
    print("  排序副本 =", s.sorted_values())

    # TODO: 第二段演示（实现后补）

    print("=== 空数据约定 ===")
    empty = NaiveStats()
    print("  空均值 =", empty.mean())
    print("  空中位数 =", empty.median())


if __name__ == "__main__":
    main()
