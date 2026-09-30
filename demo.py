"""treeindset 现状演示。

第一段: 建一棵小树, 看枚举选法求出的最大独立集与最小点覆盖。
第二段: 预留的树形动态规划演示位子 (见文末注释)。
"""

from treeindset import TreeSolve


def build_path(n):
    """建一条 n 个顶点的链 0-1-...-(n-1)。"""
    t = TreeSolve(n)
    for v in range(n - 1):
        t.add_edge(v, v + 1)
    return t


def build_star(n):
    """建一棵 n 个顶点的星形, 中心是零号, 其余都是叶子。"""
    t = TreeSolve(n)
    for v in range(1, n):
        t.add_edge(0, v)
    return t


def main():
    print("=== 朴素树求解器 (枚举选法) ===")
    path = build_path(6)
    print(f"  path4 edges      = {build_path(4).edges()}")
    print(f"  path6 MIS        = {path.max_independent_set()}")
    print(f"  path6 MIS size   = {path.independent_size()}")
    print(f"  path6 MVC        = {path.min_vertex_cover()}")

    star = build_star(5)
    print(f"  star5 MIS        = {star.max_independent_set()}")
    print(f"  star5 MVC        = {star.min_vertex_cover()}")
    print(f"  star5 is_cover   = {star.is_vertex_cover([0])}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
