"""unionfind 现状演示。

第一段：登记若干元素，做几次合并与查询，看朴素搬移口径给出的连通关系、
组件统计、带权偏移与回滚结果。
第二段：预留的迭代演示位子（见文末注释）。
"""

from unionfind.core import UnionFind


def main():
    print("=== 并查集与动态连通性（现有朴素能力） ===")
    uf = UnionFind()
    for x in range(6):
        uf.add(x)
    print("  登记元素:", uf.elements())
    uf.union(0, 1)
    uf.union(2, 3)
    uf.union(1, 2)
    print("  合并后连通 0 与 3:", uf.connected(0, 3))
    print("  各集合:", uf.groups())
    print("  组件个数:", uf.component_count(), " 大小:", uf.component_sizes())
    print("  0 所在集合大小:", uf.size(0))

    uf.union_weighted(4, 5, 7)
    print("  4 相对 5 的偏移:", uf.relate(4, 5))

    print("  已生效合并次数:", uf.history_len())
    print("  累计搬移次数:", uf.count_moves())
    uf.undo()
    print("  撤销一次后 4 与 5 是否连通:", uf.connected(4, 5))
    uf.rollback_to(0)
    print("  回滚到最初后 0 与 3 是否连通:", uf.connected(0, 3))
    print("  回滚后连通性快照 0 与 1:", uf.connected_at(0, 0, 1))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
