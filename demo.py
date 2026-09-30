"""WeightedGraph 现状演示。

第一段：搭一张小的带权图，跑朴素最短路，打印各点距离、前驱与一条最短路径。
第二段：预留的堆优化与交叉核对演示位子（见文末注释）。
"""

from wgraph.shortest import WeightedGraph


def main():
    print("=== 朴素最短路 ===")
    g = WeightedGraph(directed=True)
    g.add_edge("s", "a", 4)
    g.add_edge("s", "b", 1)
    g.add_edge("b", "a", 2)
    g.add_edge("a", "c", 5)
    g.add_edge("b", "c", 8)

    dist = g.shortest_distances("s")
    print(f"  距离: {dist}")

    pred = g.shortest_predecessors("s")
    print(f"  前驱: {pred}")

    path = g.shortest_path("s", "c")
    total = 0
    for i in range(1, len(path)):
        for nxt, w in g.neighbors(path[i - 1]):
            if nxt == path[i]:
                total += w
    print(f"  路径: {path} 权值和={total}")
    print(f"  点数={g.node_count()} 边数={g.edge_count()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
