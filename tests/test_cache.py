"""ValueCache 现有行为的锁定测试。"""

import unittest

from revcache.cache import CacheError, ValueCache


class ValueCacheTest(unittest.TestCase):

    def setUp(self):
        self.cache = ValueCache()

    def test_put_then_get(self):
        self.cache.put("k", 1)
        self.assertEqual(self.cache.get("k"), 1)

    def test_get_absent_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.cache.get("nope")

    def test_put_overwrites(self):
        self.cache.put("k", 1)
        self.cache.put("k", 2)
        self.assertEqual(self.cache.get("k"), 2)
        self.assertEqual(len(self.cache), 1)

    def test_invalidate_reports_whether_entry_existed(self):
        self.cache.put("k", 1)
        self.assertTrue(self.cache.invalidate("k"))
        self.assertFalse(self.cache.invalidate("k"))
        with self.assertRaises(KeyError):
            self.cache.get("k")

    def test_capacity_evicts_least_recently_used(self):
        cache = ValueCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        self.assertEqual(sorted(cache.keys()), ["a", "c"])
        self.assertEqual(cache.stats()["evictions"], 1)

    def test_injected_write_fault_raises_then_recovers(self):
        self.cache.inject_write_faults(2)
        with self.assertRaises(CacheError):
            self.cache.put("k", 1)
        with self.assertRaises(CacheError):
            self.cache.put("k", 1)
        self.cache.put("k", 1)
        self.assertEqual(self.cache.get("k"), 1)
        self.assertEqual(self.cache.stats()["write_errors"], 2)

    def test_items_are_oldest_first(self):
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.assertEqual(self.cache.items(), [("a", 1), ("b", 2)])

    def test_stats_snapshot(self):
        stats = self.cache.stats()
        for name in ("puts", "hits", "misses", "invalidations",
                     "evictions", "write_errors"):
            self.assertIn(name, stats)


if __name__ == "__main__":
    unittest.main()
