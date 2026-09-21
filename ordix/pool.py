"""节点池：复用节点对象，并把分配与回收计数暴露出来。

release 只把对象挂回空闲链，不清内容；acquire 拿到手后由调用方用
nodes.reset 清理。live 是当前还被用着的节点数，等于 acquire 次数
减 release 次数：节点被丢掉忘了还，live 就会一直涨；重复归还则会让
live 比真实值小。
"""

from .nodes import InternalNode, LeafNode


class NodePool:
    def __init__(self):
        self._free_leaves = []
        self._free_internals = []
        self._created = 0
        self._acquires = 0
        self._releases = 0
        self._reused = 0

    def acquire(self, leaf):
        """取一个节点，类型由 leaf 指定。"""
        self._acquires += 1
        free = self._free_leaves if leaf else self._free_internals
        if free:
            self._reused += 1
            return free.pop()
        self._created += 1
        if leaf:
            return LeafNode(self._created)
        return InternalNode(self._created)

    def release(self, node):
        """把节点还回池子，等待再次分配。"""
        if node is None:
            return
        node.parent = None
        self._releases += 1
        if node.is_leaf:
            self._free_leaves.append(node)
        else:
            self._free_internals.append(node)

    def stats(self):
        return {
            "created": self._created,
            "reused": self._reused,
            "acquires": self._acquires,
            "releases": self._releases,
            "live": self._acquires - self._releases,
            "free": len(self._free_leaves) + len(self._free_internals),
        }
