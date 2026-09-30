"""mincut 现状演示。

第一段：用枚举边子集这一条朴素路演示求最小割、判断某组边是不是割、判断给定容
量下有没有更小的割，并打印枚举边子集计数；
第二段：预留的最大流分层增广、收缩合并与规模对照演示位子（见文末注释）。
"""

from mincut.naive import (
    CutTools,
    edge_subset_count,
    feasible_cut,
    global_min_cut_value,
    is_cut,
    min_cut,
)


def main():
    print("=== 朴素枚举边子集 ===")
    # 四节点有向图：边编号 0 到 5。
    edges = [
        (0, 1, 3, 0),
        (0, 2, 2, 1),
        (1, 3, 2, 2),
        (2, 3, 3, 3),
        (1, 2, 1, 4),
        (2, 1, 1, 5),
    ]
    cut = min_cut(edges, 0, 3, directed=True)
    print("  最小割容量 %d" % cut["capacity"])
    print("  源侧集合 %s" % cut["source_side"])
    print("  割边编号 %s" % cut["cut_edges"])

    print("  割边集合是不是割 %s" % is_cut(edges, 0, 3, cut["cut_edges"]))
    weak = feasible_cut(edges, 0, 3, 1, directed=True)
    print("  容量不超过一是否可行 %s" % (weak is not None))
    print("  边表组数上的子集总数 %d" % edge_subset_count(edges))

    print("  无向全局最小割容量 %d" % global_min_cut_value([
        (0, 1, 1, 0),
        (1, 2, 2, 1),
        (0, 2, 3, 2),
    ]))

    tools = CutTools(edges, directed=True)
    tools.reset_subset_count()
    tools.min_cut(0, 3)
    print("  六条边枚举子集次数 %d" % tools.subset_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 mincut 里补出最大流分层增广路、收缩合并路与独立枚举印证路之后，在这
    # 里加一段演示：对同一批图用三条路各求一遍最小割容量、源侧集合与割边编号，
    # 逐项对照结果是否一致；再演示增补的判断某组边是不是割、判断给定容量下有没
    # 有割两个能力，与各自朴素路逐项比对；并排打印最大流增广次数与朴素枚举子集
    # 次数，覆盖源汇相等、单边、平行边、零容量边、完全不连通、有向无向两种口径
    # 这些边界，确认多路结论一致。


if __name__ == "__main__":
    main()
