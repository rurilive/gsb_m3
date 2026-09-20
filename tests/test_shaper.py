"""TokenBucketShaper 新行为测试。

全部用注入的手动时钟，精确对上补充点、就绪点与等待上限，
不依赖真实时间。基线测试 tests/test_limiter.py 原样保留。
"""

import unittest

from shapeq.shaper import TokenBucketShaper, REJECT, QUEUE


class ManualClock:
    """可推进的假时钟，测试里精确控制补充时刻。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def drain(s, clock, seconds, step=0.01):
    """推进时钟并逐拍 pump，模拟时间流逝下的自动放行。"""
    elapsed = 0.0
    while elapsed < seconds - 1e-9:
        dt = min(step, seconds - elapsed)
        clock.advance(dt)
        elapsed += dt
        s.pump(clock.now)


class TestTokenBucket(unittest.TestCase):
    def test_burst_up_to_capacity_passes(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=3, clock=clock)
        for _ in range(3):
            self.assertTrue(s.acquire("a").allowed)
        r = s.acquire("a")
        self.assertFalse(r.allowed)
        self.assertEqual(r.reason, "rate_limited")

    def test_refill_at_configured_rate(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=2.0, capacity=3, clock=clock)
        for _ in range(3):
            s.acquire("a")
        clock.advance(0.5)            # 补 1 个令牌
        self.assertTrue(s.acquire("a").allowed)
        self.assertFalse(s.acquire("a").allowed)

    def test_refill_is_capped_at_capacity(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=2, clock=clock)
        clock.advance(100.0)          # 闲置再久也不超过桶容量
        self.assertTrue(s.acquire("a").allowed)
        self.assertTrue(s.acquire("a").allowed)
        self.assertFalse(s.acquire("a").allowed)

    def test_refill_boundary_exclusive(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        clock.advance(0.999)          # 差一点，令牌还没补到
        self.assertFalse(s.acquire("a").allowed)
        clock.advance(0.001)
        self.assertTrue(s.acquire("a").allowed)


class TestTenantFairness(unittest.TestCase):
    def test_one_tenant_starving_itself_does_not_block_others(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=2, clock=clock)
        for _ in range(5):
            s.acquire("hog")          # hog 把自己打满并持续吃拒
        for _ in range(2):
            self.assertTrue(s.acquire("calm").allowed)
        self.assertEqual(s.stats()["tokens_by_tenant"]["calm"], 0.0)

    def test_tenants_refill_independently(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=2, clock=clock)
        s.acquire("a")
        s.acquire("a")
        clock.advance(1.0)
        self.assertTrue(s.acquire("a").allowed)
        self.assertTrue(s.acquire("b").allowed)  # b 是新租户，整桶可用
        self.assertTrue(s.acquire("b").allowed)


class TestQueue(unittest.TestCase):
    def test_queued_request_is_served_after_wait(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        r = s.acquire("a")
        self.assertTrue(r.queued)
        self.assertEqual(s.stats()["queued"], 1)
        clock.advance(1.0)
        s.pump(clock.now)
        r.wait()
        self.assertTrue(r.allowed)
        self.assertAlmostEqual(r.waited, 1.0, places=6)
        self.assertEqual(s.stats()["queued"], 0)

    def test_queue_is_fifo_per_tenant(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        r1 = s.acquire("a")
        r2 = s.acquire("a")
        clock.advance(1.0)
        s.pump(clock.now)             # 只够放队头
        r1.wait()
        self.assertTrue(r1.allowed)
        self.assertEqual(r2.status, "queued")
        clock.advance(1.0)
        s.pump(clock.now)
        r2.wait()
        self.assertTrue(r2.allowed)

    def test_queue_does_not_cross_tenants(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        ra = s.acquire("a")           # a 排队
        # b 与 a 的队列无关，立即拿到整桶
        self.assertTrue(s.acquire("b").allowed)
        drain(s, clock, 1.0)
        ra.wait()
        self.assertTrue(ra.allowed)

    def test_max_wait_rejects_before_entering_queue(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE,
                              max_wait=1.0, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        self.assertTrue(s.acquire("a").queued)       # 等 1s，恰好上限
        r = s.acquire("a")                           # 需等 2s，超上限
        self.assertEqual(r.status, "rejected")
        self.assertEqual(r.reason, "max_wait_exceeded")
        self.assertEqual(s.stats()["queued"], 1)

    def test_max_queue_rejects_when_full(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE,
                              max_queue=2, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        self.assertTrue(s.acquire("a").queued)
        self.assertTrue(s.acquire("a").queued)
        r = s.acquire("a")
        self.assertEqual(r.status, "rejected")
        self.assertEqual(r.reason, "queue_full")
        self.assertEqual(s.stats()["queued"], 2)

    def test_reserved_tokens_not_given_to_later_requests(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=1, overflow=QUEUE, clock=clock)
        self.assertTrue(s.acquire("a").allowed)
        r = s.acquire("a")           # 预占下一个令牌
        clock.advance(1.0)
        # 不 pump：到点的令牌属于队头，新来的不能拿
        self.assertTrue(s.acquire("a").queued)
        s.pump(clock.now)
        r.wait()
        self.assertTrue(r.allowed)


class TestStats(unittest.TestCase):
    def test_stats_reports_all_fields(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=2, overflow=QUEUE, clock=clock)
        s.acquire("a")
        s.acquire("a")
        s.acquire("a")                # 排队（预占 a 的下一个令牌）
        s.acquire("b")                # 新租户：整桶可用
        s.acquire("hog")              # 新租户：整桶可用
        st = s.stats()
        self.assertEqual(st["allowed"], 4)
        self.assertEqual(st["queued"], 1)
        self.assertAlmostEqual(st["tokens_remaining"], 2.0, places=6)
        self.assertAlmostEqual(st["tokens_by_tenant"]["a"], 0.0, places=6)
        self.assertAlmostEqual(st["tokens_by_tenant"]["b"], 1.0, places=6)
        self.assertAlmostEqual(st["tokens_by_tenant"]["hog"], 1.0, places=6)
        self.assertEqual(st["tenants"], 3)

    def test_stats_returns_fresh_dict_and_refills_lazily(self):
        clock = ManualClock()
        s = TokenBucketShaper(rate=1.0, capacity=2, clock=clock)
        s.acquire("a")
        clock.advance(1.0)
        st = s.stats()
        st["allowed"] = 99
        st["tokens_by_tenant"]["a"] = 99
        again = s.stats()
        self.assertEqual(again["allowed"], 1)
        self.assertAlmostEqual(again["tokens_by_tenant"]["a"], 2.0, places=6)


class TestValidation(unittest.TestCase):
    def test_invalid_rate_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(rate=0, capacity=1)

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(rate=1, capacity=0)

    def test_invalid_overflow_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(rate=1, capacity=1, overflow="block")

    def test_invalid_amount_raises(self):
        s = TokenBucketShaper(rate=1, capacity=1)
        with self.assertRaises(ValueError):
            s.acquire("a", amount=0)


if __name__ == "__main__":
    unittest.main()
