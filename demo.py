"""konig 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from konig.graph import NaiveGraph, SelfLoopError


def baseline_demo():
    g = NaiveGraph(left=["a", "b", "c"], right=["x", "y"])
    g.add_edge("a", "x")
    g.add_edge("b", "x")
    g.add_edge("b", "y")
    g.add_edge("c", "y")

    print("左侧点:", g.left_points())
    print("右侧点:", g.right_points())
    print("边数:", g.edge_count())
    print("最大匹配边集:", g.naive_max_matching())
    print("最大匹配边数:", g.naive_matching_size())
    print("朴素点覆盖:", g.naive_min_vertex_cover())

    try:
        bad = NaiveGraph(left=["v"], right=["v"])
        bad.add_edge("v", "v")
    except SelfLoopError as exc:
        print("自环被拒:", exc)


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：柯尼希定理求最小点覆盖与独立集 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
