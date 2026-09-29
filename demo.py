"""graphex 现状演示。

第一段：在无权图上判断连通。
第二段：预留的迭代演示位子（见文末注释）。
"""

from graphex.matrix import ReachMatrix


def main():
    print("=== 无权连通（现有能力） ===")
    g = ReachMatrix(["a", "b", "c", "d", "e"])
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    print(f"  nodes()             -> {g.nodes()}")
    print(f"  reached_from(a)     -> {g.reached_from('a')}")
    print(f"  connected(a, d)     -> {g.connected('a', 'd')}")
    print(f"  connected(a, e)     -> {g.connected('a', 'e')}")

    # TODO(带权最短路改造): 带权最短路实现后，在这里加一段演示：
    # 给若干条边配上非负权重，调用带权最短路接口算出单源到各点的
    # 最短距离与路径，打印路径上的节点序列及其向量距离；
    # 再给一个目标点集演示全部到达后的提前终止，
    # 并对一个带负权边的图演示 fail fast 的报错。


if __name__ == "__main__":
    main()
