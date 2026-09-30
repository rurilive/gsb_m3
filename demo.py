"""treediam 现状演示。

第一段：朴素统计——枚举点对求直径与端点，逐点遍历求最远点、重心与距离之和。
第二段：预留的两趟遍历、树形动态规划与规模对照演示位子（见文末注释）。
"""

from treediam import (
    Tree,
    all_distance_sums,
    center,
    centroid,
    diameter,
    diameter_path,
    farthest_from,
    pair_distance_sum,
)


def build_sample():
    """一段样例：根 1，一条主链 1-2-3-4，3 号上挂两个叶子 5、6。"""
    t = Tree(1)
    t.add_edge(1, 2)
    t.add_edge(2, 3)
    t.add_edge(3, 4)
    t.add_edge(3, 5)
    t.add_edge(3, 6)
    return t


def main():
    t = build_sample()
    print("=== 朴素统计（枚举所有点对与逐点遍历） ===")
    print(f"  节点 {t.nodes()}，点对共 {len(t.pairs())} 对")

    length, a, b = diameter(t)
    print(f"  直径长度 {length}，端点 {a} 与 {b}")
    print(f"  直径路径 {diameter_path(t)}")

    far_node, far_dist = farthest_from(t, 6)
    print(f"  离 6 最远的点 {far_node}，距离 {far_dist}")

    print(f"  重心 {centroid(t)}，中心 {center(t)}")
    print(f"  所有点对距离之和 {pair_distance_sum(t)}")
    sums = all_distance_sums(t)
    print(f"  各点距离之和 {sums}")

    # TODO: 第二段演示（实现后补）
    # 两趟遍历求直径与端点路径、树形动态规划求直径（向下最长与次长链合并，
    # 互相印证）、按边贡献求点对距离之和、换根求某点到所有点距离之和、重心
    # （含两重心取编号小者）都补齐后，在这里加一段演示：同一棵树上把两趟遍历路
    # 与树形动态规划路的结果逐项打印对照；顺手打印朴素路与升级路各跑了多少次
    # 遍历，给出规模对照。


if __name__ == "__main__":
    main()
