"""treehash 现状演示。

第一段：朴素同构判定与规范哈希。看有根同构、无根同构、一棵树的规范哈希、
一组树按同构分组，再打印朴素分组这趟要做的两两递归比较次数规模。
第二段：预留的树哈希与括号序列两路新做法的演示位子（见文末注释）。
"""

from treehash import (
    canonical_hash,
    group_isomorphic,
    pairwise_comparison_count,
    rooted_canonical_hash,
    rooted_isomorphic,
    unrooted_isomorphic,
)
from treehash.shapes import chain, mirrored, relabel, star


def build_sample():
    """一条五节点链、一棵四叶星形，以及它们各自重编号后的同构副本。"""
    line = chain(5)
    fan = star(4)
    line_copy = relabel(line, [4, 3, 2, 1, 0])
    fan_copy = mirrored(4)
    return line, fan, line_copy, fan_copy


def main():
    line, fan, line_copy, fan_copy = build_sample()

    print("=== 朴素同构判定与规范哈希 ===")
    print("  链树两端为根的子树是否同构:", rooted_isomorphic(line, 0, line, 4))
    print("  链树端点与中点两棵子树是否同构:", rooted_isomorphic(line, 0, line, 2))
    print("  链树与其重编号副本是否同构(无根):", unrooted_isomorphic(line, line_copy))
    print("  星形树与其镜像副本是否同构(无根):", unrooted_isomorphic(fan, fan_copy))
    print("  星形树与链树是否同构(无根):", unrooted_isomorphic(fan, line))

    print("  链树以端点 0 为根的规范哈希:", rooted_canonical_hash(line, 0))
    print("  链树以端点 4 为根的规范哈希:", rooted_canonical_hash(line, 4))
    print("  链树无根规范哈希:", canonical_hash(line))
    print("  链树副本无根规范哈希:", canonical_hash(line_copy))

    bunch = [line, fan, line_copy, fan_copy]
    print("  一组树的下标分组:", group_isomorphic(bunch))
    print("  朴素分组两两递归比较次数:", pairwise_comparison_count(bunch))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
