"""offx 现状演示。

第一段：造一份序列与一小批区间查询，逐条现场重扫，看答案与重扫计数；
第二段：预留的离线排序与增量结构演示位子（见文末注释）。
"""

from offx.batch import QueryBatch, answer_queries, scan_visits


def main():
    print("=== 逐查询现场重扫 ===")
    values = [3, 1, 4, 1, 5, 9, 2, 6]
    queries = [(0, 2), (4, 7), (1, 6), (5, 5)]
    batch = QueryBatch(values)
    batch.reset_scan_count()
    sums = []
    for q in queries:
        sums.append(batch.range_sum(q[0], q[1]))
    print("  序列 %d 个元素，查询 %d 条" % (batch.size(), len(queries)))
    print("  区间和 %s" % (sums,))
    print("  重扫计数 %d，逐查询口径估算 %d" % (
        batch.scan_count, scan_visits(queries)))
    print("  不同元素个数全区间 %d" % batch.range_distinct(0, 7))
    print("  逐项一致 %s" % (answer_queries(values, queries, "sum"),))

    # TODO(离线排序与增量结构): 在 offx 里补出按右端点排序配树状数组的离线回答、
    # 以及按端点分块排序移动指针的莫队或分块之后，在这里加一段演示：同一批查询
    # 用两条新路径各答一遍，打印逐项是否与暴力口径一致，并比较指针移动次数与
    # 逐查询重扫次数的差距，说明离线复用把总代价压下来了。


if __name__ == "__main__":
    main()
