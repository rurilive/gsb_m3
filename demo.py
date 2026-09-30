"""boruvka 现状演示。

第一段：给一张带权无向图，看朴素实现扫出来的最小生成森林与权值。
第二段：预留的博鲁夫卡演示位子（见文末注释）。
"""

from boruvka.mst import (
    components,
    is_connected,
    mst_edges,
    mst_weight,
)


def main():
    print("=== 朴素最小生成森林（现有能力） ===")
    n = 6
    edges = [
        (0, 1, 4),
        (1, 2, 8),
        (2, 3, 7),
        (3, 4, 9),
        (4, 5, 10),
        (5, 0, 2),
        (1, 5, 6),
        (2, 5, 7),
        (3, 5, 14),
        (0, 0, 3),
        (1, 2, 8),
    ]
    print("  节点数       =", n)
    print("  边表         =", edges)
    print("  连通         =", is_connected(n, edges))
    print("  分量划分     =", components(n, edges))
    picked = mst_edges(n, edges)
    for i in picked:
        print("  选边下标     =", i, "边 =", edges[i])
    print("  所选的边     =", [edges[i] for i in picked])
    print("  总权值       =", mst_weight(n, edges))

    print("=== 不连通图上的最小生成森林 ===")
    split = [(0, 1, 2), (1, 2, 3), (3, 4, 1)]
    print("  连通         =", is_connected(5, split))
    print("  分量划分     =", components(5, split))
    print("  森林权值     =", mst_weight(5, split))

    # TODO(博鲁夫卡): 博鲁夫卡算法就位后，在这里加一段演示：对上面同一张
    # 图调用新入口得到所选边与权值，再调用克鲁斯卡尔那条独立路径，把两条
    # 路子的边集合、总权值与连通性判断并排打印，让两者肉眼可见地对得上。


if __name__ == "__main__":
    main()
