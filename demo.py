"""mattree 现状演示。

第一段：拿几个小图，用暴力枚举子集的路子连通性、度数序列与生成树计数；
第二段：预留的矩阵树定理改造演示位子（见文末注释）。
"""

from mattree.count import (
    count_spanning_trees,
    degrees,
    enumerate_trees,
    is_connected,
    is_spanning_tree,
)


def main():
    print("=== 暴力生成树计数 ===")
    triangle = [(0, 1), (1, 2), (2, 0)]
    print("  三角形连通 %s" % is_connected(3, triangle))
    print("  三角形度数 %s" % degrees(3, triangle))
    print("  三角形是树 %s" % is_spanning_tree(3, triangle))
    print("  三角形生成树个数 %d" % count_spanning_trees(3, triangle))
    print("  三角形全部生成树 %s" % enumerate_trees(3, triangle))

    four = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    print("  完全四边形生成树个数 %d" % count_spanning_trees(4, four))

    two = [(0, 1), (0, 1)]
    print("  两节点重边生成树个数 %d" % count_spanning_trees(2, two))

    split = [(0, 1), (2, 3)]
    print("  不连通图生成树个数 %d" % count_spanning_trees(4, split))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
