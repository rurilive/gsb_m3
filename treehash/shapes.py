"""常见树形的构造助手，供演示与测试摆出可复现的输入。

这里只负责按固定规则把边连起来，不做任何同构判定；判定一律走包内的朴素
两两递归比较。所有构造都确定性：同样的入参每次都得到同一棵树。
"""

from . import Tree


def single():
    """孤立的单节点树。"""
    return Tree(1)


def empty():
    """空树，没有任何顶点。"""
    return Tree(0)


def chain(n):
    """0-1-2-...-(n-1) 一条链。"""
    tree = Tree(n)
    for i in range(n - 1):
        tree.add_edge(i, i + 1)
    return tree


def star(leaves):
    """0 号顶点为中心，1 到 leaves 为叶子的星形树。"""
    tree = Tree(leaves + 1)
    for i in range(1, leaves + 1):
        tree.add_edge(0, i)
    return tree


def balanced(n):
    """顶点按层序铺满的近似完全二叉树，父为 i，左右子为 2i+1 与 2i+2。"""
    tree = Tree(n)
    for child in range(1, n):
        tree.add_edge((child - 1) // 2, child)
    return tree


def relabel(tree, perm):
    """按顶点重编号构造一棵与 tree 同构的树。

    perm[i] 是新树里顶点 i 的新编号，必须是一个排列。原来 i 与 j 有边，新树
    里 perm[i] 与 perm[j] 有边。用来制造形状相同、编号不同的对照输入。
    """
    new_tree = Tree(tree.n)
    for u, v in tree.edges():
        new_tree.add_edge(perm[u], perm[v])
    return new_tree


def mirrored(leaves):
    """星形树的镜像编号版本：中心落在最大编号上，与 star 同构。"""
    tree = star(leaves)
    n = tree.n
    return relabel(tree, [n - 1 - i for i in range(n)])
