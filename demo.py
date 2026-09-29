"""FlatSorted 现状演示。

第一段：插入、查找、删除、排名、按排名取元素、闭区间扫描。
第二段：预留的跳表演示位子（见文末 TODO 注释）。
"""

from skiplib.sorted import FlatSorted


def main():
    print("=== 有序集合（有序 list） ===")
    s = FlatSorted()
    for x in (5, 1, 4, 2, 3, 3):
        s.add(x)
    print("  len           = %s" % (len(s),))
    print("  contains(4)   = %s" % (s.contains(4),))
    print("  contains(9)   = %s" % (s.contains(9),))
    print("  rank(4)       = %s" % (s.rank(4),))
    print("  kth(0)        = %s" % (s.kth(0),))
    print("  range(2, 4)   = %s" % (s.range_query(2, 4),))
    s.discard(3)
    print("  discard(3)    = %s" % (s.range_query(1, 5),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
