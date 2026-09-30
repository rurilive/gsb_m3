"""matchx 演示脚本。

第一段：跑一遍基线功能（枚举求最大匹配、判定完美匹配、导出最小点
覆盖与最大独立集），可直接运行；
第二段：实现后补（见文末注释）。
"""

from matchx.bipartite import BipartiteMatcher


def baseline_demo():
    m = BipartiteMatcher()
    m.add_edge("l1", "r1")
    m.add_edge("l1", "r2")
    m.add_edge("l2", "r1")
    m.add_edge("l3", "r2")

    print("左侧点:", sorted(m.left_nodes))
    print("右侧点:", sorted(m.right_nodes))
    print("边数:", m.edge_count())
    print("最大匹配条数:", m.max_matching_size())
    print("是否存在完美匹配:", m.perfect_matching_exists())
    print("一个最大匹配:", m.max_matching())
    print("l1 配到:", m.matched_to("l1"))
    cover = m.min_vertex_cover()
    print("最小点覆盖:", sorted(cover), "大小", len(cover))
    iset = m.max_independent_set()
    print("最大独立集:", sorted(iset), "大小", len(iset))


def main():
    print("== 第一段：基线枚举能力 ==")
    baseline_demo()
    print("== 第二段：增广路匹配与由它导出的覆盖、独立集 ==")
    # TODO: 第二段演示（实现后补）
    # 实现后在这里补一段：换一张稍大的图，先跑增广路求最大匹配，打印增广
    # 提交次数与访问边数，再打印由最大匹配导出的最小点覆盖与最大独立集，
    # 并用同一批数据把新老两条路的结果对一遍，确认条数与方案都一致。


if __name__ == "__main__":
    main()
