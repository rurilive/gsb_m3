"""segmerge 快速演示。

第一段直跑改造前的基线：一棵小树，每个节点挂一个小权值集合，自底向上
把子节点的集合逐个元素搬进父节点，合并完排一次序，再在这只排序桶上从
头扫出某权值出现次数、前几大之和、不同权值个数、排名与第几小，并报出
累计的朴素搬移次数。
第二段预留给改造后的高效路径演示，待实现补齐。
"""

from segmerge.dynamic import MergeTree


def demo_baseline():
    print("== 基线：子节点集合逐个元素搬进父节点 ==")
    parents = [-1, 0, 0, 1, 1]
    weights = [[5], [2, 2], [7], [-3], []]
    t = MergeTree(parents, weights)
    print("节点数 =", t.node_count(), " 根 =", t.root())

    for node_id in range(t.node_count()):
        print("节点", node_id, "合并后 =", t.merged_values(node_id))

    print("根上权值2出现次数 =", t.count_of(0, 2))
    print("根上前2大之和 =", t.topk_sum(0, 2))
    print("根上不同权值个数 =", t.distinct_count(0))
    print("根上权值2的排名 =", t.rank_of(0, 2))
    print("根上第3小 =", t.kth_smallest(0, 3))
    print("整树合并结果 =", t.merge_report())
    print("累计朴素搬移次数 =", t.naive_moves())


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
