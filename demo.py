"""flownet 现状演示。

第一段：用单路增广与枚举边子集这两条朴素路演示求最大流、求最小割、判断某组边是
不是割、判断给定容量下有没有更小的割，并打印单路增广次数与枚举子集计数；
第二段：预留的分层多路增广、残量图构造割与规模对照演示位子（见文末注释）。
"""

from flownet import (
    FlowTools,
    edge_subset_count,
    feasible_cut,
    is_cut,
    max_flow,
    min_cut,
)


def main():
    print("=== 朴素单路增广与枚举边子集 ===")
    # 四节点有向图：边编号 0 到 3，最大流与最小割容量都是四。
    edges = [
        (0, 1, 3, 0),
        (0, 2, 2, 1),
        (1, 3, 2, 2),
        (2, 3, 3, 3),
    ]

    flow = max_flow(edges, 0, 3)
    print("  最大流值 %d" % flow.value)
    print("  单路增广次数 %d" % flow.augmentations)
    print("  各边流量 %s" % flow.flows)

    cut = min_cut(edges, 0, 3)
    print("  最小割容量 %d" % cut["capacity"])
    print("  源侧集合 %s" % cut["source_side"])
    print("  割边编号 %s" % cut["cut_edges"])

    print("  割边集合是不是割 %s" % is_cut(edges, 0, 3, cut["cut_edges"]))
    weak = feasible_cut(edges, 0, 3, 3)
    print("  容量不超过三是否可行 %s" % (weak is not None))
    print("  边表组数上的子集总数 %d" % edge_subset_count(edges))

    tools = FlowTools(edges, 0, 3)
    tools.reset_augment_count()
    tools.reset_subset_count()
    tools.max_flow()
    tools.min_cut()
    print("  工具累计单路增广次数 %d" % tools.augment_count())
    print("  工具累计枚举子集次数 %d" % tools.subset_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 flownet 里补出分层图多路增广、当前弧优化与残量图直接构造最小割之后，在
    # 这里加一段演示：对同一批网络用单路与多路两条路径各求一遍最大流值、最小割
    # 容量、源侧集合与割边编号，逐项对照结果是否一致；再演示增补的容量下界可行
    # 流、最小费用最大流与最大流最小割对偶断言这些独立能力，与各自对照口径逐项
    # 比对；并排打印多路增广的轮数与单路增广次数，覆盖源汇相等、单边、平行边、
    # 零容量边、完全不连通这些边界，确认多路结论一致。


if __name__ == "__main__":
    main()
