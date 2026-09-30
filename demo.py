"""dsutree 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from dsutree.core import DsuTree


def baseline_demo():
    # 一棵小树：0 为根，0 连 1 与 2，1 连 3 与 4
    tree = DsuTree()
    tree.load(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [0, 1, 0, 1, 2])

    print("结点个数:", tree.node_count())
    print("结点 0 子树颜色频次:", tree.subtree_counts(0))
    print("结点 0 的主色:", tree.dominant_color(0))
    print("结点 1 子树颜色频次:", tree.subtree_counts(1))
    print("结点 1 的主色:", tree.dominant_color(1))
    print("全部主色:", tree.all_dominant_colors())
    print("朴素访问次数:", tree.visit_count())


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：小并大启发式与逐项对照 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
