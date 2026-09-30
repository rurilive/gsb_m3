"""treedpx 现状演示。

第一段：载入一棵小树，看暴力枚举给出的最大价值与最优选择。
第二段：预留的迭代演示位子（见文末注释）。
"""

from treedpx.core import TreeKnapsack


def main():
    print("=== 树上背包（现有暴力枚举能力） ===")
    nodes = {"a": (1, 1), "b": (1, 2), "c": (1, 3), "d": (2, 5)}
    parent = {"a": None, "b": "a", "c": "a", "d": "c"}
    k = TreeKnapsack()
    k.load(nodes, parent)
    print("  节点:", k.nodes())
    print("  d 的父节点:", k.parent_of("d"))
    print("  容量 3 的最大价值:", k.brute_force_best(3))
    print("  一组最优选择:", k.brute_force_selection(3))
    print("  容量 3 的可行方案数:", k.feasible_count(3))
    print("  暴力枚举规模:", k.brute_force_scale())

    # TODO(子树合并的容量动态规划): 逐节点把自身容量贡献进来、再按容量卷积
    # 合并各孩子子树表的实现补齐后，在这里加一段演示：对同一棵树分别用暴力与
    # 状态表两条路径求最大价值、最优选择与可行方案数，打印两边结果确认逐项一致；
    # 再打印状态表规模，与暴力枚举规模对照，展示规模差距；接着演示森林（加虚拟
    # 根连成一棵树）与多重背包（节点有选择次数上限）两种扩展口径。


if __name__ == "__main__":
    main()
