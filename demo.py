"""orderstat 现状演示。

第一段：用一个固定序列跑一遍现状的朴素次序统计，看第几个最小、前几个
最小之和、中位数与两序列中位数，以及回放一串查询后的逐步返回值；
第二段：预留的快速选择与堆维护演示位子（见文末注释）。
"""

from orderstat.seq import Selector


def main():
    print("=== 朴素全排序取次序统计量 ===")
    data = [7, -3, 3, -8, 0, 5, 3, -1, 12, 3]
    s = Selector(data)
    print("  序列 %s，长度 %d" % (data, s.size()))
    print("  排序后 %s" % s.sorted_copy())

    print("  第 0 个最小 %d" % s.select_kth(0))
    print("  第 4 个最小 %d" % s.select_kth(4))
    print("  第 9 个最小 %d" % s.select_kth(9))

    print("  前 0 个最小之和 %d" % s.smallest_sum(0))
    print("  前 3 个最小之和 %d" % s.smallest_sum(3))
    print("  前 10 个最小之和 %d" % s.smallest_sum(10))

    print("  中位数 %s" % s.median())
    print("  与 [3, 9] 合并后的中位数 %s" % s.pairwise_median([3, 9]))

    queries = [
        ("kth", 4),
        ("smallest", 3),
        ("median",),
        ("pairwise", [3, 9]),
        ("kth", 0),
    ]
    final, results = Selector.replay(data, queries)
    print("  回放 %d 步，逐返回值 %s" % (len(queries), results))
    print("  回放末态 %s" % final)

    # TODO: 第二段演示（实现后补）
    # 快速选择与堆维护实现后，在这里加一段演示：拿一批第几个最小、前几个
    # 最小之和、两序列中位数的查询，用快速选择加三路划分与堆维护的路径一次
    # 性回答，打印每个查询的结果，并打印选择路与全排序路的比较次数计数，
    # 与朴素全排序路径的比较次数放在一起对照，确认差距明显。


if __name__ == "__main__":
    main()
