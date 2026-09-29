"""molib 现状演示。

第一段：用一个固定数组跑一遍现状的逐项重扫查询，看不同值个数、众数
出现次数与出现次数平方和，并打印朴素代价；
第二段：预留的莫队演示位子（见文末注释）。
"""

from molib.offline import BruteQueries


def main():
    print("=== 逐项重扫 ===")
    data = [1, 2, 1, 3, 2, 1, 4, 2]
    q = BruteQueries(data)
    print("  数组 %s，长度 %d" % (data, q.size()))

    queries = [(0, 8), (0, 3), (2, 6), (6, 8), (4, 4)]
    for l, r in queries:
        print(
            "  区间 [%d, %d)：不同值 %d，众数出现次数 %d，平方和 %d，朴素代价 %d"
            % (
                l,
                r,
                q.distinct(l, r),
                q.mode_count(l, r),
                q.sum_of_squares(l, r),
                q.brute_cost(l, r),
            )
        )

    # TODO: 第二段演示（实现后补）
    # 莫队实现后，在这里加一段演示：拿一批不同值个数与众数查询，用莫队一次性
    # 回答，打印每个查询的结果，并打印左右指针移动总次数，与逐项重扫的朴素代价
    # 总和放在一起对照，确认指针移动量明显更小。


if __name__ == "__main__":
    main()
