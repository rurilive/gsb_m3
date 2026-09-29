"""unionx 现状演示。

第一段：朴素连通判定——加边后每次查询现场跑一遍广度优先遍历。
第二段：预留的并查集、组件统计与回滚演示位子（见文末注释）。
"""

from unionx import NaiveUnionFind, UnknownNode


def main():
    print("=== 朴素连通判定（现场 BFS） ===")
    uf = NaiveUnionFind()
    for name in ("a", "b", "c", "d"):
        uf.add_node(name)
    uf.add_edge("a", "b")
    uf.add_edge("b", "c")

    print(f"  a 与 c 连通：{uf.connected('a', 'c')}")
    print(f"  a 与 d 连通：{uf.connected('a', 'd')}")
    print(f"  a 所在组件：{uf.component_of('a')}")
    print(f"  组件个数：{uf.component_count()}，各组件大小：{uf.component_sizes()}")

    try:
        uf.connected("a", "ghost")
    except UnknownNode as exc:
        print(f"  未知节点 -> {exc.__class__.__name__}({exc.node!r})")

    # TODO(带压缩与按秩合并的并查集、组件统计、撤销回滚、带权关系、离线批量):
    # 换成一个增量维护的并查集后，在这里加一段演示：
    # 打印几个 union 之后的 find 结果与组件大小；
    # union 后撤回一次，打印组件数变回去；
    # 带权合并后打印两点间的相对关系；
    # 最后喂一批 union 与查询，打印按声明顺序得到的离线批量结果。


if __name__ == "__main__":
    main()
