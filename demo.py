"""rmqlib 现状演示。

第一段：构造一个整数序列，逐个区间求最小值、最大值与最小值的下标。
第二段：预留的迭代演示位子（见文末注释）。
"""

from rmqlib.rmq import NaiveRMQ


def main():
    print("=== 朴素区间最值（现有能力） ===")
    q = NaiveRMQ([5, 2, 8, 1, 9, 3, 7])
    print(f"  序列             -> {q.as_list()}")
    print(f"  长度             -> {len(q)}")
    ranges = [(0, 7), (0, 1), (1, 4), (3, 3), (4, 7)]
    for l, r in ranges:
        print(
            f"  [{l}, {r})  min/max/argmin -> "
            f"{q.query_min(l, r)} / {q.query_max(l, r)} / {q.query_argmin(l, r)}"
        )
    print(f"  批量最小值       -> {q.query_many(ranges)}")

    # TODO: 第二段演示（实现后补）
    # 稀疏表改造完成后，在这里补一轮演示：
    # 对同一序列用稀疏表求区间最小值与最大值，并对一个二维矩阵求子矩阵最大值；
    # 把稀疏表结果与上面的逐项扫描结果并排打印，展示两条路口径一致。


if __name__ == "__main__":
    main()
