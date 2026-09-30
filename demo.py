"""NaivePercentileStream 现状演示。

第一段：朴素流式分位统计的推入、中位数、分位数与排序副本。
第二段：预留的在线双堆中位数与分位数演示位子（见文末注释）。
"""

from pctstream.stream import NaivePercentileStream


def main():
    print("=== 朴素流式分位统计（现有能力） ===")
    s = NaivePercentileStream()
    for x in (12.0, 4.0, 30.0, 18.0, 7.0):
        s.push(x)
    print("  个数 =", s.count())
    print("  中位数 =", s.median())
    print("  分位 0 =", s.quantile(0))
    print("  分位 50 =", s.quantile(50))
    print("  分位 100 =", s.quantile(100))
    print("  最小值 =", s.min())
    print("  最大值 =", s.max())
    print("  排序副本 =", s.sorted_values())

    # TODO: 第二段演示（实现后补）

    print("=== 空数据约定 ===")
    empty = NaivePercentileStream()
    print("  空中位数 =", empty.median())
    print("  空分位 50 =", empty.quantile(50))


if __name__ == "__main__":
    main()
