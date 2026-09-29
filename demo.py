"""graphiq 现状演示。

第一段：建一张有向图，看朴素全对可达给出的结果。
第二段：预留的分析演示位子（见文末注释）。
"""

from graphiq.graph import Graph


def main():
    print("=== 朴素全对可达（现有能力） ===")
    g = Graph(
        nodes=["s", "a", "b", "t"],
        edges=[("s", "a"), ("a", "b"), ("b", "a"), ("b", "t")],
    )
    print("  nodes           =", g.nodes())
    print("  edges           =", g.edges())
    print("  reachable(s)    =", sorted(g.reachable("s")))
    print("  reachable(t)    =", sorted(g.reachable("t")))
    all_pairs = g.reachable_all()
    for node in g.nodes():
        print("  reachable_all   %s -> %s" % (node, sorted(all_pairs[node])))

    # TODO(分析能力): 强连通分量、拓扑与环、桥与割点、最短路径族就位后，
    # 在这里加一段演示：先打印这张图的强连通分量与压缩后的 DAG，
    # 再对同一张图打印从 s 到 t 的最短路径与距离，并给出无权图下
    # 由宽度优先搜索得到的另一条最短路，对照两次结果是否一致。


if __name__ == "__main__":
    main()