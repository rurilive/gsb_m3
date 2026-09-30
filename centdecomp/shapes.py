"""常见树形的构造助手，供演示与测试摆出可复现的输入。

这里只负责按固定规则把边连起来，不做任何统计；统计一律走包内的朴素路径
枚举。所有构造都确定性：同样的入参每次都得到同一棵树。
"""

from . import Tree


def single():
    """孤立的单节点树。"""
    return Tree(1)


def chain(n, weight=1):
    """0-1-2-...-(n-1) 一条链，每条边长都是 weight。"""
    tree = Tree(n)
    for i in range(n - 1):
        tree.add_edge(i, i + 1, weight)
    return tree


def star(leaves, weight=1):
    """0 号顶点为中心，1 到 leaves 为叶子的星形树。"""
    tree = Tree(leaves + 1)
    for i in range(1, leaves + 1):
        tree.add_edge(0, i, weight)
    return tree


def balanced(n, weight=1):
    """顶点按层序铺满的近似完全二叉树，父为 i，左右子为 2i+1 与 2i+2。"""
    tree = Tree(n)
    for child in range(1, n):
        tree.add_edge((child - 1) // 2, child, weight)
    return tree
