"""分片器的现有实现。

当前只有一个最朴素的取模分片器 ModShard：维护一张节点列表，key 交给固定
哈希得到整数，再对节点个数取模，余数决定该 key 落在哪一个节点上。做法简单，
但节点数量一变，几乎所有 key 的取模余数都会改变，归属大面积重排；节点之间
也没有虚拟节点或权重，负载只能听天由命。

这里没有环、没有虚拟节点、没有副本概念，删除节点也未提供。
"""

import hashlib


def _hash(text):
    """把字符串映射成 64 位整数，取值稳定，便于跨进程复现。"""
    digest = hashlib.md5(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class ModShard:
    """按键哈希对节点个数取模的分片器。

    add_node 的顺序决定节点在列表中的下标；owner 用 key 的哈希对当前节点数
    取模，取对应下标的节点；空分片器返回 None。
    """

    def __init__(self):
        self._nodes = []

    def add_node(self, node):
        """把一个物理节点加入分片器。重复加入同一节点不产生新副本。"""
        if not isinstance(node, str) or not node:
            raise ValueError("node must be a non-empty string")
        if node in self._nodes:
            return
        self._nodes.append(node)

    def owner(self, key):
        """返回 key 归属的节点；空分片器返回 None。"""
        if not self._nodes:
            return None
        h = _hash(key)
        return self._nodes[h % len(self._nodes)]

    def nodes(self):
        """当前分片器上的物理节点，按名字排序。"""
        return sorted(self._nodes)
