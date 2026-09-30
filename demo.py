"""maxflow 现状演示。

第一段：建一张小网络，用现有朴素实现求最大流与最小割，看值是否相等。
第二段：预留的分层阻断流演示位子（见文末注释）。
"""

from maxflow import FlowNetwork, max_flow, min_cut


def build():
    """一张五节点的小网络，最大流为 5。"""
    net = FlowNetwork()
    net.add_edge("s", "a", 3)
    net.add_edge("s", "b", 2)
    net.add_edge("a", "b", 1)
    net.add_edge("a", "t", 2)
    net.add_edge("b", "t", 3)
    return net


def main():
    print("=== 朴素最大流与最小割（现有能力） ===")
    net = build()
    flow = max_flow(net, "s", "t")
    print("  最大流值  =", flow.value)
    print("  增广次数  =", flow.augmentations)
    print("  各边流量  =",
          [(e.src, e.dst, e.flow) for e in flow.edges])

    cut = min_cut(net, "s", "t")
    print("  最小割值  =", cut.value)
    print("  源点侧    =", cut.source_side)
    print("  汇点侧    =", cut.sink_side)
    print("  割边      =", [(e.src, e.dst, e.capacity) for e in cut.cut_edges])
    print("  两值一致  =", flow.value == cut.value)

    # TODO(阻塞流改造): 分层图上的阻塞流与一次性推多条增广路就位后，
    # 在这里加一段演示：对同一批网络，分别用新老两条路径各跑一遍，
    # 逐项对照最大流值与最小割划分是否一致，并打印两条路径的增广次数
    # 与分层轮数，把规模放大后的差距摆出来；顺带覆盖无流、单边、平行边、
    # 自环、最大流转整数、割集不唯一这些边界。


if __name__ == "__main__":
    main()
