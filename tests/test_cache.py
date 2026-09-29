"""LFUCache 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：读写、频次淘汰与并列时取最久未使用、
peek 无副作用、统计计数、非法容量的构造期拒绝。
新增行为（过期、频次衰减、加权淘汰、驱逐窗口）另建测试文件，不改动本文件。
"""

import unittest

from lfukit.cache import LFUCache


class TestGetAndPut(unittest.TestCase):
    def test_get_missing_returns_none(self):
        c = LFUCache(2)
        self.assertIsNone(c.get("absent"))

    def test_put_then_get(self):
        c = LFUCache(2)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_get_increments_frequency(self):
        c = LFUCache(2)
        c.put("a", 1)
        c.get("a")
        c.get("a")
        self.assertEqual(c._entries["a"].freq, 3)

    def test_put_existing_key_updates_and_bumps_frequency(self):
        c = LFUCache(2)
        c.put("a", 1)
        c.put("a", 2)
        self.assertEqual(c.get("a"), 2)
        self.assertEqual(len(c), 1)
        self.assertEqual(c._entries["a"].freq, 3)

    def test_contains_and_len_and_keys(self):
        c = LFUCache(3)
        c.put("a", 1)
        c.put("b", 2)
        self.assertIn("a", c)
        self.assertNotIn("z", c)
        self.assertEqual(len(c), 2)
        self.assertEqual(c.keys(), ["a", "b"])


class TestPeek(unittest.TestCase):
    def test_peek_does_not_touch_stats(self):
        c = LFUCache(2)
        c.put("a", 1)
        before = c.stats()
        self.assertEqual(c.peek("a"), 1)
        self.assertEqual(c.stats(), before)

    def test_peek_missing_returns_none(self):
        self.assertIsNone(LFUCache(2).peek("absent"))


class TestEviction(unittest.TestCase):
    def test_evicts_least_frequent(self):
        c = LFUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        self.assertIsNone(c.peek("b"))
        self.assertEqual(c.peek("a"), 1)
        self.assertEqual(c.peek("c"), 3)

    def test_tie_broken_by_least_recently_used(self):
        c = LFUCache(3)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        # 三者次数相同，a 最久未使用
        c.put("d", 4)
        self.assertIsNone(c.peek("a"))
        self.assertEqual(sorted(c.keys()), ["b", "c", "d"])

    def test_lru_tie_after_touch(self):
        c = LFUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # a 最新
        c.put("c", 3)
        self.assertIsNone(c.peek("b"))


class TestStats(unittest.TestCase):
    def test_counters(self):
        c = LFUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.get("zzz")
        s = c.stats()
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["evicted"], 0)
        self.assertEqual(s["size"], 2)
        self.assertEqual(s["capacity"], 2)

    def test_evicted_counter(self):
        c = LFUCache(1)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.stats()["evicted"], 1)


class TestCapacityGuard(unittest.TestCase):
    def test_zero_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LFUCache(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LFUCache(-3)


if __name__ == "__main__":
    unittest.main()