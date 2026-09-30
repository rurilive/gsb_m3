"""eulerx 现状演示。

第一段：朴素一笔画——枚举全部边顺序的排列，逐个检查首尾相接且每条边恰好
走一次，判断有无欧拉路径或欧拉回路并给出一条具体的路径，同时打印要检查的
边序总数与字符串接龙的排列个数。
第二段：预留的两条独立做法与规模对照演示位子（见文末注释）。
"""

from eulerx import (
    chain_count,
    has_euler_circuit_undirected,
    has_euler_path_undirected,
    make_undirected,
    naive_edge_order_check_count,
    naive_euler_circuit_undirected,
    naive_euler_path_undirected,
)


def build_sample():
    """一段样例：四边形 0-1-2-3-0 再补一条对角线 0-2，恰有两个奇度点 0 与 2。"""
    g = make_undirected()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]:
        g.add_edge(u, v)
    return g


def main():
    g = build_sample()
    print("=== 朴素一笔画（枚举全部边序逐个检查） ===")
    print(f"  顶点 {g.vertices()}，边 {g.undirected_edges()}")
    print(f"  点到度 {g.degree()}，奇度点 {g.odd_degree_vertices()}")
    print(f"  求一次路径要检查 {naive_edge_order_check_count(g)} 个边序")

    print(f"  有无欧拉路径 {has_euler_path_undirected(g)}")
    print(f"  有无欧拉回路 {has_euler_circuit_undirected(g)}")
    print(f"  一条欧拉路径 {naive_euler_path_undirected(g)}")
    print(f"  一条欧拉回路 {naive_euler_circuit_undirected(g)}")

    dominoes = ["ab", "bc", "cd"]
    print(f"  字符串接龙 {dominoes} 的可行排列个数 {chain_count(dominoes)}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
