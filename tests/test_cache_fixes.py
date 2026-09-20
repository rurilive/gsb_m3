"""缓存雪崩相关修复的回归测试。"""

import random
import unittest

from avalcache.cache import TtlCache


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestPutManyJitter(unittest.TestCase):
    def test_expiry_times_are_spread(self):
        clock = FakeClock()
        c = TtlCache(clock=clock, rng=random.Random(7))
        c.put_many([(f"k{i}", i) for i in range(20)], ttl=100)
        expires = [c.expires_at(f"k{i}") for i in range(20)]
        self.assertEqual(len(set(expires)), len(expires))
        self.assertGreater(max(expires) - min(expires), 5)

    def test_jitter_stays_within_bounds(self):
        clock = FakeClock()
        c = TtlCache(clock=clock, jitter=0.1, rng=random.Random(1))
        c.put_many([(f"k{i}", i) for i in range(50)], ttl=100)
        for i in range(50):
            remaining = c.expires_at(f"k{i}") - clock.now
            self.assertGreaterEqual(remaining, 90 - 1e-9)
            self.assertLessEqual(remaining, 110 + 1e-9)

    def test_zero_jitter_keeps_one_expiry_time(self):
        clock = FakeClock()
        c = TtlCache(clock=clock, jitter=0)
        c.put_many([("a", 1), ("b", 2)], ttl=60)
        self.assertEqual(c.expires_at("a"), clock.now + 60)
        self.assertEqual(c.expires_at("b"), clock.now + 60)

    def test_put_is_not_jittered(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        c.put("a", 1, ttl=60)
        self.assertEqual(c.expires_at("a"), clock.now + 60)

    def test_put_many_without_ttl_never_expires(self):
        c = TtlCache(clock=FakeClock())
        c.put_many([("a", 1), ("b", 2)])
        self.assertIsNone(c.expires_at("a"))
        self.assertIsNone(c.expires_at("b"))


class TestSweep(unittest.TestCase):
    def test_sweep_removes_expired_and_counts(self):
        clock = FakeClock()
        c = TtlCache(clock=clock, jitter=0)
        c.put("a", 1, ttl=10)
        c.put("b", 2, ttl=30)
        c.put("c", 3, ttl=10)
        clock.advance(10)
        self.assertEqual(c.sweep(), 2)
        self.assertEqual(c.stats()["entries"], 1)
        self.assertEqual(c.stats()["expired"], 2)
        self.assertEqual(c.get("b"), 2)

    def test_sweep_idempotent(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        c.put("a", 1, ttl=10)
        clock.advance(11)
        self.assertEqual(c.sweep(), 1)
        self.assertEqual(c.sweep(), 0)

    def test_sweep_clears_batch_then_requests_hit_after_reload(self):
        clock = FakeClock()
        c = TtlCache(clock=clock, jitter=0)
        c.put_many([(f"k{i}", i) for i in range(4)], ttl=30)
        clock.advance(30)
        self.assertEqual(c.sweep(), 4)
        calls = []
        c.get_or_load("a", lambda k: calls.append(k) or {"k": k}, ttl=30)
        c.get_or_load("a", lambda k: calls.append(k) or {"k": k}, ttl=30)
        self.assertEqual(len(calls), 1)


class TestLoaderFailure(unittest.TestCase):
    def test_loader_exception_is_not_cached(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        attempts = []

        def flaky(key):
            attempts.append(key)
            raise RuntimeError("503")

        with self.assertRaises(RuntimeError):
            c.get_or_load("a", flaky, ttl=60)
        with self.assertRaises(RuntimeError):
            c.get_or_load("a", flaky, ttl=60)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(c.stats()["entries"], 0)
        self.assertIsNone(c.expires_at("a"))
        self.assertEqual(c.stats()["loads"], 2)

    def test_recovery_after_loader_comes_back(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)

        def boom(key):
            raise RuntimeError("503")

        with self.assertRaises(RuntimeError):
            c.get_or_load("a", boom, ttl=60)

        def healthy(key):
            return {"ok": True}

        self.assertEqual(c.get_or_load("a", healthy, ttl=60), {"ok": True})
        self.assertEqual(c.get_or_load("a", boom, ttl=60), {"ok": True})
        self.assertEqual(c.stats()["loads"], 2)
        self.assertEqual(c.stats()["hits"], 1)


class TestOverwriteRecomputesTtl(unittest.TestCase):
    def test_overwrite_uses_fresh_ttl(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        c.put("a", 1, ttl=60)
        clock.advance(50)
        c.put("a", 2, ttl=60)
        self.assertEqual(c.expires_at("a"), clock.now + 60)
        clock.advance(50)
        self.assertEqual(c.get("a"), 2)

    def test_overwrite_without_ttl_becomes_eternal(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        c.put("a", 1, ttl=10)
        c.put("a", 2)
        self.assertIsNone(c.expires_at("a"))
        clock.advance(10_000)
        self.assertEqual(c.get("a"), 2)

    def test_overwrite_eternal_with_ttl_gains_expiry(self):
        clock = FakeClock()
        c = TtlCache(clock=clock)
        c.put("a", 1)
        c.put("a", 2, ttl=30)
        self.assertEqual(c.expires_at("a"), clock.now + 30)


if __name__ == "__main__":
    unittest.main()
