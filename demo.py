"""rangeq 现状演示。

第一段：用一个固定序列跑一遍现状的朴素区间操作，看区间加、区间求和、
区间最值与单点读改，以及回放一串操作后的末态；
第二段：预留的分块演示位子（见文末注释）。
"""

from rangeq.seq import Query


def main():
    print("=== 朴素逐元素处理 ===")
    data = [3, -1, 4, 1, 5, -9, 2, 6]
    q = Query(data)
    print("  序列 %s，长度 %d" % (data, q.size()))

    print("  区间 [0, 8) 求和 %d" % q.sum(0, 8))
    print("  区间 [2, 5) 求和 %d" % q.sum(2, 5))
    print("  区间 [0, 8) 最小值 %d，最大值 %d" % (q.min_val(0, 8), q.max_val(0, 8)))

    q.add(0, 4, 1)
    print("  区间 [0, 4) 每个位置加 1 后 %s" % q.data)

    q.set(3, 100)
    print("  单点 set(3, 100) 后 get(3) 得到 %d" % q.get(3))

    ops = [
        ("sum", 0, 8),
        ("add", 0, 2, 1),
        ("min", 0, 4),
        ("max", 0, 4),
        ("get", 3),
    ]
    final, results = Query.replay(data, ops)
    print("  回放 %d 步，逐返回值 %s" % (len(ops), results))
    print("  回放末态 %s" % final)

    # TODO: 第二段演示（实现后补）
    # 分块实现后，在这里加一段演示：拿一批区间加、区间求和、区间最值与单点
    # 查询，用分块路径一次性回答，打印每个查询的结果，并打印块数与被访问元素
    # 计数，与朴素路径逐元素处理的总访问量放在一起对照，确认差距明显。


if __name__ == "__main__":
    main()
