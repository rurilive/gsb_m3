"""B+ 树节点。

数据只放叶子，内部节点只做路由。内部节点的第 i 个键等于第 i 个
孩子子树里的最小键，即 len(keys) == len(children) 恒成立，查找
时用 bisect_right(keys, key) 减一选孩子。
"""


class Node:
    """叶子与内部节点的公共部分。"""

    __slots__ = ("keys", "parent", "slot")

    is_leaf = False

    def __init__(self, slot):
        self.keys = []
        self.parent = None
        self.slot = slot

    def __repr__(self):
        kind = "Leaf" if self.is_leaf else "Internal"
        return "<%s #%d keys=%r>" % (kind, self.slot, self.keys)


class LeafNode(Node):
    """叶子：keys 与 values 一一对应，next/prev 串成升序链。"""

    __slots__ = ("values", "next", "prev")

    is_leaf = True

    def __init__(self, slot):
        Node.__init__(self, slot)
        self.values = []
        self.next = None
        self.prev = None


class InternalNode(Node):
    """内部节点：keys[i] 是 children[i] 子树的最小键。"""

    __slots__ = ("children",)

    def __init__(self, slot):
        Node.__init__(self, slot)
        self.children = []


def reset(node):
    """把节点清回出厂状态，池子里捞出来的旧节点必须先过这一道。"""
    node.keys = []
    node.parent = None
    if node.is_leaf:
        node.values = []
        node.next = None
        node.prev = None
    else:
        node.children = []
    return node
