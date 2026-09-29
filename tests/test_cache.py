"""LRUCache 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：单层条目数上限的 LRU、命中和未命中的返回
形态、覆盖写、主动淘汰、按键列出与统计计数，以及非法容量的构造期拒绝。
新增行为（两级缓存、降级与提升、TTL、回写队列、分层统计与并发一致）另建
测试文件，不改动本文件。
"""

import unittest

from cascadectl.cache import LRUCache


class TestGetPut(unittest.TestCase):
    def test_miss_returns_false_none(self):
        c = LRUCache(2)
        self.assertEqual(c.get("absent"), (False, None))

    def test_put_then_get_hit(self):
        c = LRUCache(2)
        self.assertEqual(c.put("a", 1), 1)
        self.assertEqual(c.get("a"), (True, 1))

    def test_put_overwrites_value(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("a", 2)
        self.assertEqual(c.get("a"), (True, 2))
        self.assertEqual(len(c), 1)

    def test_get_updates_recency(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # a 变最新，b 最久未用
        self.assertEqual(c.keys(), ["b", "a"])


class TestEviction(unittest.TestCase):
    def test_put_beyond_capacity_evicts_lru(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertNotIn("a", c)
        self.assertIn("b", c)
        self.assertIn("c", c)

    def test_evict_returns_least_recently_used(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.evict(), "a")

    def test_evict_empty_returns_none(self):
        self.assertIsNone(LRUCache(2).evict())

    def test_evicted_counter(self):
        c = LRUCache(1)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.stats()["evicted"], 1)


class TestPeekAndKeys(unittest.TestCase):
    def test_peek_does_not_change_recency(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.peek("a"), 1)
        self.assertEqual(c.keys(), ["a", "b"])

    def test_peek_missing_returns_none(self):
        self.assertIsNone(LRUCache(2).peek("absent"))

    def test_keys_oldest_first(self):
        c = LRUCache(3)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        c.get("a")
        self.assertEqual(c.keys(), ["b", "c", "a"])


class TestStats(unittest.TestCase):
    def test_counters(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.get("a")
        c.get("missing")
        s = c.stats()
        self.assertEqual(s["capacity"], 2)
        self.assertEqual(s["size"], 1)
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["evicted"], 0)

    def test_contains(self):
        c = LRUCache(2)
        c.put("a", 1)
        self.assertIn("a", c)
        self.assertNotIn("b", c)


class TestCapacityGuard(unittest.TestCase):
    def test_zero_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LRUCache(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LRUCache(-3)


if __name__ == "__main__":
    unittest.main()