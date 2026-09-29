"""一致性哈希环的现有实现。

把 key 稳定地映射到环上的某台节点：节点按哈希值排成环，key 取环上顺时针
第一个不小于自身哈希的节点，越过末尾则回绕到环首。当前每个物理节点在环上
只占一个位置，不支持虚拟节点、权重与删除。
"""

import bisect
import hashlib


def _hash(text):
    """把字符串映射成 64 位整数，取值稳定，便于跨进程复现。"""
    digest = hashlib.md5(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class HashRing:
    """基础一致性哈希环。

    每个 add_node 的节点在环上占一个位置；lookup 返回顺时针第一个不小于
    key 哈希的节点，空环返回 None。
    """

    def __init__(self):
        self._hashes = []
        self._owners = []

    def add_node(self, node):
        """把一个物理节点加入环。重复加入同一节点不产生新位置。"""
        if not isinstance(node, str) or not node:
            raise ValueError("node must be a non-empty string")
        h = _hash(node)
        if h in self._hashes:
            return
        i = bisect.bisect_left(self._hashes, h)
        self._hashes.insert(i, h)
        self._owners.insert(i, node)

    def lookup(self, key):
        """返回 key 归属的节点；空环返回 None。"""
        if not self._hashes:
            return None
        h = _hash(key)
        i = bisect.bisect_left(self._hashes, h)
        if i == len(self._hashes):
            i = 0
        return self._owners[i]

    def nodes(self):
        """当前环上的物理节点，按名字排序。"""
        return sorted(set(self._owners))
