"""topocount 现状演示。

第一段：用全排列枚举回答一张小图的拓扑序问题，数拓扑序个数、取字典序最小
的拓扑序、看最大权值和与顶点出现位置区间，并打出枚举次数；
第二段：预留的入度法、集合划分记忆化与优先队列演示位子，见文末注释。
"""

import math

from topocount.dag import DAGCounter, brute_permutations


def main():
    print("=== 全排列枚举 ===")
    n = 4
    edges = [(0, 2), (1, 2), (2, 3)]
    g = DAGCounter(n, edges)
    print("  点数 %d，边数 %d" % (g.node_count(), g.edge_count()))
    print("  是否存在拓扑序 %r" % (g.has_topological_order(),))
    print("  拓扑序个数 %d" % (g.count_topological_orders(),))
    print("  字典序最小拓扑序 %s" % (g.min_topological_order(),))
    print("  全部拓扑序 %s" % (g.topological_orders(),))
    print("  最大权值和与序列 %s" % (g.max_weight_order([1, 1, 1, 1]),))
    print("  位置区间 %s" % (g.position_ranges(),))
    g.reset_counters()
    g.count_topological_orders()
    print("  数一遍的计数 %s" % (g.counters(),))

    cg = DAGCounter(3, [(0, 1), (1, 2), (2, 0)])
    print("  有环时是否有拓扑序 %r" % (cg.has_topological_order(),))
    print("  有环时最小拓扑序 %s" % (cg.min_topological_order(),))

    print("  全排列规模对照 %s" % (brute_permutations(n, edges),))
    print("  规模二十的全排列次数理论值 %d" % (math.factorial(20),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
