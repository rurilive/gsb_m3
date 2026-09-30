"""kdx 现状演示。

第一段：用朴素实现做最近邻、k 近邻与范围查询，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from kdx.tree import PointSet, nearest_pair, radius_count


def main():
    print("=== 朴素最近邻与 k 近邻（现有能力） ===")
    ps = PointSet([
        (0.0, 0.0),
        (1.0, 0.0),
        (0.0, 1.0),
        (2.0, 2.0),
        (3.0, 1.0),
    ])
    idx, dist = ps.nearest((0.1, 0.2))
    print(f"  nearest((0.1,0.2))    -> 下标 {idx}，距离 {dist:.4f}")
    print(f"  knearest(..., 3)       -> {ps.knearest((0.0, 0.0), 3)}")

    print("=== 朴素范围查询（现有能力） ===")
    print(f"  rect[(0,0)-(1,1)]      -> {ps.range_query_rect((0.0, 0.0), (1.0, 1.0))}")
    print(f"  ball((0,0),1.0)        -> {ps.range_query_ball((0.0, 0.0), 1.0)}")

    print("=== 朴素统计（现有能力） ===")
    print(f"  nearest_pair()         -> {nearest_pair(ps.points)}")
    print(f"  radius_count(...,1.0)  -> {radius_count(ps.points, (0.0, 0.0), 1.0)}")
    print(f"  pruning_count          -> {ps.pruning_count}")

    # TODO: 第二段演示（实现后补）
    # 说明：kd 树实现后，在这里补一段演示——先用同一个点集建树，把最近邻、
    # k 近邻、矩形与球范围查询的剪枝计数打印出来；再逐项断言新树的返回结果
    # 与上面朴素路径完全一致，并演示朴素路径仍然保留可对照。


if __name__ == "__main__":
    main()
