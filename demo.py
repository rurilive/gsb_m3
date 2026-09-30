"""centroid 现状演示。

第一段：载入一棵小树，看朴素枚举给出的子树规模、重心、两点距离与路径计数。
第二段：预留的迭代演示位子（见文末注释）。
"""

from centroid.core import TreeCentroid


def main():
    print("=== 树的重心与树上路径（现有朴素枚举能力） ===")
    n = 4
    edges = [(0, 1, 3), (1, 2, 4), (2, 3, 5)]
    t = TreeCentroid()
    t.load(n, edges)
    print("  结点:", t.nodes())
    print("  以 0 为根的子树规模:", t.subtree_size(0))
    print("  删掉 1 后的连通块:", t.component_sizes(1))
    print("  重心:", t.centroid())
    print("  全部重心:", t.centroids())
    print("  结点 0 到 3 的距离与最大权:", t.path_stats(0, 3))
    print("  距离不超过 7 的点对数:", t.count_paths_within(7))
    print("  朴素规模:", t.brute_scale(), " 点对规模:", t.brute_pair_scale())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
