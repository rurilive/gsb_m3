"""DictCache 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：无界字典的写入与读回、命中与未命中的返回
形态、覆盖写保留访问计数，以及访问计数的累加口径。新增行为（容量约束、
LRU 与 LFU 淘汰、TTL 过期、容量与统计、并发一致）另建测试文件，不改动本文件。
"""

import unittest

from cachely.cache import DictCache


class TestGetSet(unittest.TestCase):
    def test_miss_returns_false_none(self):
        c = DictCache()
        self.assertEqual(c.get("absent"), (False, None))

    def test_set_then_get_hit(self):
        c = DictCache()
        self.assertEqual(c.set("a", 1), 1)
        self.assertEqual(c.get("a"), (True, 1))

    def test_set_overwrites_value(self):
        c = DictCache()
        c.set("a", 1)
        c.set("a", 2)
        self.assertEqual(c.get("a"), (True, 2))
        self.assertEqual(len(c), 1)

    def test_no_capacity_limit(self):
        c = DictCache()
        for i in range(100):
            c.set("k%d" % i, i)
        self.assertEqual(len(c), 100)


class TestAccessCount(unittest.TestCase):
    def test_hit_increments_access_count(self):
        c = DictCache()
        c.set("a", 1)
        c.get("a")
        c.get("a")
        self.assertEqual(c.access_count("a"), 2)

    def test_miss_does_not_increment(self):
        c = DictCache()
        c.set("a", 1)
        c.get("missing")
        self.assertEqual(c.access_count("a"), 0)

    def test_unknown_key_returns_zero(self):
        c = DictCache()
        self.assertEqual(c.access_count("never"), 0)

    def test_overwrite_keeps_access_count(self):
        c = DictCache()
        c.set("a", 1)
        c.get("a")
        c.set("a", 2)
        self.assertEqual(c.access_count("a"), 1)


class TestContainsAndLen(unittest.TestCase):
    def test_contains(self):
        c = DictCache()
        c.set("a", 1)
        self.assertIn("a", c)
        self.assertNotIn("b", c)

    def test_len(self):
        c = DictCache()
        self.assertEqual(len(c), 0)
        c.set("a", 1)
        c.set("b", 2)
        self.assertEqual(len(c), 2)


if __name__ == "__main__":
    unittest.main()
