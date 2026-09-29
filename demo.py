"""FlatIntervals 现状演示。

第一段：加入、相交、点命中、删除、全合并（当前线性扫描实现，可直接运行）。
第二段：预留的区间索引演示位子（见文末注释），实现后再补。
"""

from intervalx.tree import FlatIntervals


def main():
    print("=== 区间集合（基线）===")
    f = FlatIntervals()
    f.add(1, 5, "a")
    f.add(4, 9, "b")
    f.add(10, 12, "c")
    f.add(20, 20, "empty")

    print(f"  区间      = {f.intervals()}")
    print(f"  相交 3..6 = {f.overlaps(3, 6)}")
    print(f"  相交 9..10 (仅相接) = {f.overlaps(9, 10)}")
    print(f"  点命中 4  = {sorted(f.point_hit(4))}")
    print(f"  点命中 9  = {f.point_hit(9)}")
    print(f"  全合并    = {f.merge_all()}")

    f.remove("a")
    print(f"  删除 a 后 = {f.intervals()}")

    # TODO: 第二段演示（实现后补）
    # 区间索引实现后，在这里补一轮相交查询、点命中与全合并的演示：
    # 用同一批区间对比索引路径与基线路径的结果一致，并打印相交查询访问的节点数。


if __name__ == "__main__":
    main()
