"""centdecomp 现状演示。

第一段：朴素路径统计（枚举全部点对），看恰好距离计数、不超过计数与直径，
再打印一次朴素做法要枚举的点对规模。
第二段：预留的点分治与树形 DP 演示位子（见文末注释）。
"""

from centdecomp import count_at_most, count_exact, diameter, enumerate_pair_visits
from centdecomp.shapes import chain, star


def build_sample():
    """两棵小树：一条五节点链和一棵四叶星形。"""
    return chain(5), star(4)


def main():
    line, fan = build_sample()

    print("=== 朴素路径统计（枚举全部点对） ===")
    for name, tree in (("链树", line), ("星形树", fan)):
        print("  %s：顶点 %d，点对总数 %d" % (name, tree.n, enumerate_pair_visits(tree)))
        print("    距离恰好为 1 的点对数:", count_exact(tree, 1))
        print("    距离不超过 2 的点对数:", count_at_most(tree, 2))
        print("    直径:", diameter(tree))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
