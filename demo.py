"""rangetree 现状演示。

第一段：造一组区间，用线性扫描查一个点命中了哪几段、又访问了多少段；
第二段：预留的区间树演示位子（见文末注释）。
"""

from rangetree.set import RangeSet


def main():
    print("=== 线性扫描 ===")
    rs = RangeSet()
    for left, right in ((1, 5), (3, 8), (10, 12), (20, 24)):
        rs.insert(left, right)
    rs.reset_access_count()
    hit = rs.scan_point(4)
    print("  共 %d 段区间，点 4 命中 %d 段，访问计数 %d" % (
        rs.count(),
        len(hit),
        rs.access_count,
    ))
    print("  命中区间 %s" % (hit,))
    rs.reset_access_count()
    overlap = rs.scan_interval(11, 21)
    print("  区间 [11, 21] 命中 %d 段，访问计数 %d" % (
        len(overlap),
        rs.access_count,
    ))
    print("  命中区间 %s" % (overlap,))

    # TODO(区间树): 在 rangetree 里补出以左端点建的平衡结构与剪枝查询之后，
    # 在这里加一段演示：做一次点查询与一次区间查询，打印结果是否按左端点有序，
    # 并比较访问计数说明这次查询没有把全部区间扫一遍；再加一段重叠合并演示，
    # 打印合并后的极大不重叠区间，并说明合并前后覆盖的点集一致。


if __name__ == "__main__":
    main()