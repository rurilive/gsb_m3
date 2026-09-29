"""mcfx 快速演示。

第一段跑改造前的基线能力（最大流、单条最短路费用、可行性判断）。
第二段预留给改造后的最小费用最大流演示，待实现补齐。
"""

from mcfx.flow import FlatMcf


def build_diamond():
    """菱形图：两条 s 到 t 的并联路径，费用不同。"""
    g = FlatMcf()
    g.add_edge("s", "a", 3, 1)
    g.add_edge("s", "b", 3, 2)
    g.add_edge("a", "t", 3, 1)
    g.add_edge("b", "t", 3, 5)
    return g


def demo_baseline():
    print("== 基线：朴素增广与单条最短路 ==")
    g = build_diamond()
    flow, rough_cost = g.max_flow("s", "t")
    print("最大流 =", flow, "(只看流量，不看费用)")
    print("沿路费用合计（粗略） =", rough_cost)
    print("单条最短路费用 path_cost =", g.path_cost("s", "t"))
    print("能否送达 6 单位 =", g.has_feasible("s", "t", 6))
    print("能否送达 9 单位 =", g.has_feasible("s", "t", 9))


def demo_min_cost():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_min_cost()


if __name__ == "__main__":
    main()
