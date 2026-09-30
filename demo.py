"""shortestpath 快速演示。

第一段直跑改造前的基线：带非负权图上从源点求最短距离、回溯拼出路径、
统计不可达点，并量出每轮线性找最小的比较次数，能看出它随结点数平方增长。
第二段预留给改造后的高效路径演示，待实现补齐。
"""

from shortestpath.dijkstra import NaiveGraph


def demo_baseline():
    print("== 基线：每轮在未确定结点里线性找最小 ==")
    g = NaiveGraph([
        ("A", "B", 1),
        ("A", "C", 4),
        ("B", "C", 1),
        ("B", "D", 5),
        ("C", "D", 1),
    ])
    print("结点 =", g.nodes(), " 结点数 =", g.size())

    dist = g.distances("A")
    print("A 出发的距离表 =", dist)
    print("不可达点 =", g.unreachable("A"))

    for node, route in sorted(g.paths("A").items()):
        print("A 到", node, "的路径 =", route)

    print("A 到 D 的一条最短路 =", g.path("A", "D"))
    print("线性找最小比较次数 =", g.lookups("A"))
    print("快照 =", g.stats("A"))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
