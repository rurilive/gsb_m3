"""四处线上缺陷修复后的行为测试。基线见 test_cache.py，本文件只补新行为。"""

import unittest

from avalcache.cache import TtlCache


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestBatchExpirySpread(unittest.TestCase):
    def make(self):
        clock = FakeClock()
        return TtlCache(clock=clock), clock

    def test_put_many_spreads_expiry(self):
        c, clock = self.make()
        c.put_many([(f"k{i}", i) for i in range(5)], ttl=60)
        expiries = {c.expires_at(f"k{i}") for i in range(5)}
        self.assertEqual(len(expiries), 5)

    def test_put_many_spread_stays_in_second_half_of_window(self):
        c, clock = self.make()
        c.put_many([(f"k{i}", i) for i in range(10)], ttl=60)
        for i in range(10):
            lifetime = c.expires_at(f"k{i}") - clock.now
            self.assertGreater(lifetime, 30)
            self.assertLessEqual(lifetime, 60)

    def test_put_many_no_ttl_stays_immortal(self):
        c, _ = self.make()
        c.put_many([("a", 1), ("b", 2)])
        self.assertIsNone(c.expires_at("a"))
        self.assertIsNone(c.expires_at("b"))

    def test_put_many_accepts_generator(self):
        c, _ = self.make()
        c.put_many(((f"k{i}", i) for i in range(3)), ttl=10)
        self.assertEqual(c.stats()["entries"], 3)


class TestSweep(unittest.TestCase):
    def make(self):
        clock = FakeClock()
        return TtlCache(clock=clock), clock

    def test_sweep_removes_expired_and_counts(self):
        c, clock = self.make()
        c.put_many([(f"k{i}", i) for i in range(4)], ttl=30)
        clock.advance(60)
        self.assertEqual(c.sweep(), 4)
        s = c.stats()
        self.assertEqual(s["entries"], 0)
        self.assertEqual(s["expired"], 4)

    def test_sweep_keeps_immortal_entries(self):
        c, clock = self.make()
        c.put("a", 1)
        c.put("b", 2, ttl=10)
        clock.advance(20)
        self.assertEqual(c.sweep(), 1)
        self.assertEqual(c.get("a"), 1)


class TestLoaderFailure(unittest.TestCase):
    def make(self):
        clock = FakeClock()
        return TtlCache(clock=clock), clock

    def test_loader_exception_propagates_and_caches_nothing(self):
        c, _ = self.make()

        def boom(key):
            raise RuntimeError("下游 503")

        with self.assertRaises(RuntimeError):
            c.get_or_load("a", boom, ttl=60)
        self.assertEqual(c.stats()["entries"], 0)
        self.assertIsNone(c.get("a"))

    def test_loader_retries_after_failure(self):
        c, _ = self.make()
        calls = []

        def flaky(key):
            calls.append(key)
            if len(calls) == 1:
                raise RuntimeError("第一次失败")
            return {"key": key}

        with self.assertRaises(RuntimeError):
            c.get_or_load("a", flaky, ttl=60)
        self.assertEqual(c.get_or_load("a", flaky, ttl=60), {"key": "a"})
        self.assertEqual(calls, ["a", "a"])


class TestOverwriteRefreshesExpiry(unittest.TestCase):
    def make(self):
        clock = FakeClock()
        return TtlCache(clock=clock), clock

    def test_overwrite_recomputes_expiry(self):
        c, clock = self.make()
        c.put("a", 1, ttl=60)
        clock.advance(50)
        c.put("a", 2, ttl=60)
        self.assertEqual(c.expires_at("a"), clock.now + 60)

    def test_overwrite_with_ttl_replaces_immortal(self):
        c, clock = self.make()
        c.put("a", 1)
        c.put("a", 2, ttl=10)
        clock.advance(10)
        self.assertIsNone(c.get("a"))

    def test_overwrite_without_ttl_clears_expiry(self):
        c, clock = self.make()
        c.put("a", 1, ttl=10)
        c.put("a", 2)
        clock.advance(100)
        self.assertEqual(c.get("a"), 2)


if __name__ == "__main__":
    unittest.main()
