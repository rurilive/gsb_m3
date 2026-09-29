"""graphinc 现状演示。

第一段：建一张静态有向加权图，看最短路与拓扑序。
第二段：预留的增量演示位子（见文末注释）。
"""

import math

from graphinc.graph import DirectedWeightedGraph


def main():
    print("=== 静态图（现有能力） ===")
    g = DirectedWeightedGraph(
        nodes=["s", "a", "b", "t"],
        edges=[("s", "a", 2.0), ("s", "b", 9.0),
               ("a", "b", 1.0), ("b", "t", 2.0)],
    )
    dist = g.distances("s")
    shown = {k: v for k, v in dist.items() if not math.isinf(v)}
    print(f"  distances(s)      = {shown}")
    print(f"  shortest_path(s,t)= {g.shortest_path('s', 't')}")
    print(f"  reachable(s)      = {sorted(g.reachable('s'))}")
    print(f"  topo_order()      = {g.topo_order()}")

    # TODO(增量改造): 增删边与增量最短路就位后，在这里加一段演示：
    # 在上面这张图上删掉一条边、再加一条更短的边，打印删改前后
    # distances(t) 的变化，证明查询结果随当前图状态即时收敛。


if __name__ == "__main__":
    main()