"""TtlCache 现有行为的锁定测试。"""

import unittest

from avalcache.cache import TtlCache


class FakeClock:
    """手写假时钟，推进多少秒就是多少秒。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestTtlCache(unittest.TestCase):
    def make(self):
        clock = FakeClock()
        return TtlCache(clock=clock), clock

    def test_put_then_get(self):
        c, _ = self.make()
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_missing_returns_none_and_counts_miss(self):
        c, _ = self.make()
        self.assertIsNone(c.get("nope"))
        self.assertEqual(c.stats()["misses"], 1)

    def test_no_ttl_never_expires(self):
        c, clock = self.make()
        c.put("a", 1)
        clock.advance(10_000)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.stats()["expired"], 0)

    def test_ttl_not_yet_due(self):
        c, clock = self.make()
        c.put("a", 1, ttl=30)
        clock.advance(29)
        self.assertEqual(c.get("a"), 1)

    def test_ttl_expires_and_counts_expired(self):
        c, clock = self.make()
        c.put("a", 1, ttl=30)
        clock.advance(30)
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["expired"], 1)
        self.assertEqual(s["misses"], 1)

    def test_overwrite_keeps_latest_value(self):
        c, _ = self.make()
        c.put("a", 1)
        c.put("a", 2)
        self.assertEqual(c.get("a"), 2)

    def test_expires_at_for_new_key(self):
        c, clock = self.make()
        c.put("a", 1, ttl=30)
        self.assertEqual(c.expires_at("a"), clock.now + 30)

    def test_expires_at_none_without_ttl(self):
        c, _ = self.make()
        c.put("a", 1)
        self.assertIsNone(c.expires_at("a"))

    def test_expires_at_missing_key(self):
        c, _ = self.make()
        self.assertIsNone(c.expires_at("nope"))

    def test_put_many_stores_every_key(self):
        c, _ = self.make()
        c.put_many([("a", 1), ("b", 2), ("c", 3)], ttl=30)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(c.stats()["entries"], 3)

    def test_get_or_load_loads_once_then_hits(self):
        c, _ = self.make()
        calls = []

        def loader(key):
            calls.append(key)
            return {"key": key}

        self.assertEqual(c.get_or_load("a", loader, ttl=30), {"key": "a"})
        self.assertEqual(c.get_or_load("a", loader, ttl=30), {"key": "a"})
        self.assertEqual(calls, ["a"])
        s = c.stats()
        self.assertEqual(s["loads"], 1)
        self.assertEqual(s["hits"], 1)

    def test_get_or_load_reloads_after_expiry(self):
        c, clock = self.make()
        calls = []

        def loader(key):
            calls.append(key)
            return {"key": key}

        c.get_or_load("a", loader, ttl=10)
        clock.advance(10)
        c.get_or_load("a", loader, ttl=10)
        self.assertEqual(calls, ["a", "a"])
        self.assertEqual(c.stats()["loads"], 2)

    def test_sweep_keeps_live_entries(self):
        c, _ = self.make()
        c.put("a", 1, ttl=30)
        self.assertEqual(c.sweep(), 0)
        self.assertEqual(c.get("a"), 1)

    def test_delete(self):
        c, _ = self.make()
        c.put("a", 1)
        self.assertTrue(c.delete("a"))
        self.assertFalse(c.delete("a"))
        self.assertIsNone(c.get("a"))

    def test_stats_returns_fresh_dict(self):
        c, _ = self.make()
        s = c.stats()
        s["hits"] = 99
        self.assertEqual(c.stats()["hits"], 0)

    def test_clock_is_injectable(self):
        c = TtlCache(clock=lambda: 123.0)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)


if __name__ == "__main__":
    unittest.main()
