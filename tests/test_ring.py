"""HashRing 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：单点环、增节点、lookup 的确定性与空环返回。
新增行为（虚拟节点、权重、删除、迁移量）另建测试文件，不改动本文件。
"""

import unittest

from hashring.ring import HashRing


KEYS = [f"key-{i}" for i in range(2000)]


class TestAddNodeAndLookup(unittest.TestCase):
    def test_empty_ring_returns_none(self):
        r = HashRing()
        self.assertIsNone(r.lookup("any"))

    def test_single_node_owns_every_key(self):
        r = HashRing()
        r.add_node("node-a")
        for k in KEYS[:50]:
            self.assertEqual(r.lookup(k), "node-a")

    def test_lookup_returns_registered_node(self):
        r = HashRing()
        for n in ("node-a", "node-b", "node-c"):
            r.add_node(n)
        for k in KEYS:
            self.assertIn(r.lookup(k), {"node-a", "node-b", "node-c"})

    def test_lookup_is_deterministic(self):
        r = HashRing()
        for n in ("node-a", "node-b", "node-c"):
            r.add_node(n)
        first = [r.lookup(k) for k in KEYS]
        second = [r.lookup(k) for k in KEYS]
        self.assertEqual(first, second)

    def test_all_nodes_receive_some_keys(self):
        r = HashRing()
        for n in ("node-a", "node-b", "node-c"):
            r.add_node(n)
        used = {r.lookup(k) for k in KEYS}
        self.assertEqual(used, {"node-a", "node-b", "node-c"})


class TestAddNodeGuards(unittest.TestCase):
    def test_duplicate_add_is_noop(self):
        r = HashRing()
        r.add_node("node-a")
        r.add_node("node-a")
        self.assertEqual(r.nodes(), ["node-a"])

    def test_duplicate_add_keeps_lookup_stable(self):
        r = HashRing()
        r.add_node("node-a")
        r.add_node("node-b")
        before = [r.lookup(k) for k in KEYS]
        r.add_node("node-a")
        after = [r.lookup(k) for k in KEYS]
        self.assertEqual(before, after)

    def test_empty_node_rejected(self):
        r = HashRing()
        with self.assertRaises(ValueError):
            r.add_node("")
        with self.assertRaises(ValueError):
            r.add_node(None)

    def test_nodes_sorted_and_unique(self):
        r = HashRing()
        for n in ("node-c", "node-a", "node-b"):
            r.add_node(n)
        self.assertEqual(r.nodes(), ["node-a", "node-b", "node-c"])


class TestMembershipChange(unittest.TestCase):
    def test_add_node_changes_a_strict_subset(self):
        r = HashRing()
        for n in ("node-a", "node-b", "node-c"):
            r.add_node(n)
        before = [r.lookup(k) for k in KEYS]
        r.add_node("node-d")
        after = [r.lookup(k) for k in KEYS]
        changed = sum(1 for a, b in zip(before, after) if a != b)
        self.assertGreater(changed, 0)
        self.assertLess(changed, len(KEYS))
        for a, b in zip(before, after):
            if a != b:
                self.assertEqual(b, "node-d")


if __name__ == "__main__":
    unittest.main()
