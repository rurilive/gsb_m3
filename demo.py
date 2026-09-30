"""tarjanlca 现状演示。

第一段：搭一片小森林，用逐询问重标路径的朴素实现看最近公共祖先，
含跨连通块返回空的情形；
第二段：预留的塔扬离线解演示位子，见文末注释。
"""

from tarjanlca.tree import Tree


def main():
    print("=== 逐询问标记路径 ===")
    t = Tree({1: None, 2: 1, 3: 2, 4: 1, 5: 4, 9: None, 8: 9})
    print("  结点 %s" % (t.nodes(),))
    print("  根结点 %s" % (t.roots(),))
    print("  3 到根的路径 %s" % (t.path_to_root(3),))
    print("  3 与 5 的最近公共祖先 %r" % (t.lca(3, 5),))
    print("  3 与 4 的最近公共祖先 %r" % (t.lca(3, 4),))
    print("  1 与 3 的最近公共祖先 %r" % (t.lca(1, 3),))
    print("  3 与 8 的最近公共祖先 %r" % (t.lca(3, 8),))
    print("  一批询问 %s" % (t.lca_all([(1, 3), (3, 5), (3, 8)]),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
