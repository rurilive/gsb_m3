"""lcdecomp 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from lcdecomp.core import LongChainTree


def baseline_demo():
    # 一棵小树：0 为根，0 连 1 与 2，1 连 3 与 4
    tree = LongChainTree()
    tree.load(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [1, 1, 1, 1, 1])

    print("结点个数:", tree.node_count())
    print("结点 0 重儿子(按节点数):", tree.heuristic_child(0))
    print("结点 0 子树深度分布:", tree.depth_counts(0))
    print("结点 0 最深深度:", tree.deepest_depth(0))
    print("全树深度分布:", tree.depth_distribution())
    print("朴素合并拷贝代价:", tree.merge_cost())


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：长链剖分与逐项对照 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
