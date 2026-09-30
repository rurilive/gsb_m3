"""stoerwagner 现状演示。

第一段：用逐对点最大流这一条朴素路演示求无向图全局最小割，并用枚举切分的老路
在小图上对照，打印推流计数；
第二段：预留的斯托尔瓦格纳做法与规模对照演示位子（见文末注释）。
"""

from stoerwagner.naive import (
    MinCutTools,
    exhaustive_min_cut_value,
    max_flow_value,
    pairwise_min_cut_value,
)


def main():
    print("=== 逐对点最大流 ===")
    # 四点点团，每条边权重为一。
    edges = [
        (0, 1, 1, 0),
        (1, 2, 1, 1),
        (2, 3, 1, 2),
        (0, 3, 1, 3),
        (0, 2, 1, 4),
        (1, 3, 1, 5),
    ]
    value = pairwise_min_cut_value(edges)
    print("  全局最小割容量 %d" % value)
    print("  源点零到汇点三的最大流 %d" % max_flow_value(edges, 0, 3))
    print("  枚举切分对照 %d" % exhaustive_min_cut_value(edges))

    parallel = [
        (0, 1, 2, 0),
        (0, 1, 3, 1),
        (1, 2, 4, 2),
    ]
    print("  平行边累加后全局最小割 %d" % pairwise_min_cut_value(parallel))

    tools = MinCutTools(edges)
    tools.reset_augment_count()
    tools.global_min_cut()
    print("  四点图上累计推流次数 %d" % tools.augment_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 stoerwagner 里补出最大邻接搜索扩展与收缩合并这条路之后，在这里加一段
    # 演示：用反复扩展最后两点并合并的独立做法，与逐对点最大流路对同一批图各求
    # 一遍全局最小割，逐项对照是否完全一致；并排打印两条路各自的规模计数，覆盖
    # 两点图、链、星形、多平行边、完全图、单点图这些边界，确认多路结论一致、重
    # 复跑结果稳定。

if __name__ == "__main__":
    main()
