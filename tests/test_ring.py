"""ModShard 现有行为的锁定测试。

只覆盖当前取模分片器已经具备的能力：空分片器、单节点、多节点归属的确定性、
重复添加的幂等与增删节点后归属的变化。新增行为（一致性哈希环、虚拟节点、
副本、权重、删除）另建测试文件，不改动本文件。
"""

import unittest

from hashring.ring import ModShard


KEYS = [f"key-{i}" for i in range(2000)]


class TestOwnerAndLookup(unittest.TestCase):
    def test_empty_shard_returns_none(self):
        s = ModShard()
        self.assertIsNone(s.owner("any"))

    def test_single_node_owns_every_key(self):
        s = ModShard()
        s.add_node("node-a")
        for k in KEYS[:50]:
            self.assertEqual(s.owner(k), "node-a")

    def test_owner_returns_registered_node(self):
        s = ModShard()
        for n in ("node-a", "node-b", "node-c"):
            s.add_node(n)
        for k in KEYS:
            self.assertIn(s.owner(k), {"node-a", "node-b", "node-c"})

    def test_owner_is_deterministic(self):
        s = ModShard()
        for n in ("node-a", "node-b", "node-c"):
            s.add_node(n)
        first = [s.owner(k) for k in KEYS]
        second = [s.owner(k) for k in KEYS]
        self.assertEqual(first, second)

    def test_all_nodes_receive_some_keys(self):
        s = ModShard()
        for n in ("node-a", "node-b", "node-c"):
            s.add_node(n)
        used = {s.owner(k) for k in KEYS}
        self.assertEqual(used, {"node-a", "node-b", "node-c"})


class TestAddNodeGuards(unittest.TestCase):
    def test_duplicate_add_is_noop(self):
        s = ModShard()
        s.add_node("node-a")
        s.add_node("node-a")
        self.assertEqual(s.nodes(), ["node-a"])

    def test_duplicate_add_keeps_ownership_stable(self):
        s = ModShard()
        s.add_node("node-a")
        s.add_node("node-b")
        before = [s.owner(k) for k in KEYS]
        s.add_node("node-a")
        after = [s.owner(k) for k in KEYS]
        self.assertEqual(before, after)

    def test_empty_node_rejected(self):
        s = ModShard()
        with self.assertRaises(ValueError):
            s.add_node("")
        with self.assertRaises(ValueError):
            s.add_node(None)

    def test_nodes_sorted_and_unique(self):
        s = ModShard()
        for n in ("node-c", "node-a", "node-b"):
            s.add_node(n)
        self.assertEqual(s.nodes(), ["node-a", "node-b", "node-c"])


class TestMembershipChange(unittest.TestCase):
    def test_add_node_changes_a_strict_subset(self):
        s = ModShard()
        for n in ("node-a", "node-b", "node-c"):
            s.add_node(n)
        before = [s.owner(k) for k in KEYS]
        s.add_node("node-d")
        after = [s.owner(k) for k in KEYS]
        changed = sum(1 for a, b in zip(before, after) if a != b)
        self.assertGreater(changed, 0)
        self.assertLess(changed, len(KEYS))

    def test_add_node_reshuffles_widely(self):
        s = ModShard()
        for n in ("node-a", "node-b", "node-c"):
            s.add_node(n)
        before = [s.owner(k) for k in KEYS]
        s.add_node("node-d")
        after = [s.owner(k) for k in KEYS]
        changed = sum(1 for a, b in zip(before, after) if a != b)
        # 取模分片的病态：加一个节点，超过一半的 key 无辜改归属。
        self.assertGreater(changed, len(KEYS) // 2)


if __name__ == "__main__":
    unittest.main()
