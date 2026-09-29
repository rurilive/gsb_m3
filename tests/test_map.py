"""FlatMap 基线行为测试。

锁住最朴素单字典映射的现有行为：读写、默认值、删除、包含、
长度、键与项的快照式视图。
"""

import unittest

from shardmap.map import FlatMap


class FlatMapTest(unittest.TestCase):
    def test_set_then_get(self):
        m = FlatMap()
        m.set("a", 1)
        self.assertEqual(m.get("a"), 1)

    def test_get_missing_returns_none(self):
        m = FlatMap()
        self.assertIsNone(m.get("missing"))

    def test_get_missing_returns_default(self):
        m = FlatMap()
        self.assertEqual(m.get("missing", 42), 42)

    def test_overwrite(self):
        m = FlatMap()
        m.set("a", 1)
        m.set("a", 2)
        self.assertEqual(m.get("a"), 2)
        self.assertEqual(len(m), 1)

    def test_delete_present(self):
        m = FlatMap()
        m.set("a", 1)
        self.assertTrue(m.delete("a"))
        self.assertNotIn("a", m)

    def test_delete_absent(self):
        m = FlatMap()
        self.assertFalse(m.delete("nope"))

    def test_contains(self):
        m = FlatMap()
        m.set("a", 1)
        self.assertIn("a", m)
        self.assertNotIn("b", m)

    def test_len(self):
        m = FlatMap()
        self.assertEqual(len(m), 0)
        m.set("a", 1)
        m.set("b", 2)
        self.assertEqual(len(m), 2)

    def test_keys_and_items_are_snapshots(self):
        m = FlatMap()
        m.set("a", 1)
        keys = m.keys()
        items = m.items()
        m.set("b", 2)
        self.assertEqual(sorted(keys), ["a"])
        self.assertEqual(sorted(items), [("a", 1)])

    def test_snapshot(self):
        m = FlatMap()
        m.set("a", 1)
        snap = m.snapshot()
        m.set("b", 2)
        self.assertEqual(snap, {"a": 1})


if __name__ == "__main__":
    unittest.main()
