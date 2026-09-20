"""令牌桶整形与多租户公平的测试。

全部走注入的 ManualClock，不依赖真实时间；QUEUE 的等待通过把
sleep 接成时钟推进来驱动，补充点可以精确对齐。
"""

import unittest

from shapeq.shaper import QUEUE, REJECT, TokenBucketShaper


class ManualClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def advancing_sleep(clock):
    """sleep 不真睡，直接把假时钟推过去。"""

    def _sleep(seconds):
        clock.advance(seconds)

    return _sleep


class TestTokenBucketBasics(unittest.TestCase):
    def test_burst_up_to_capacity_passes(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=3, refill_rate=1.0, clock=clock
        )
        for _ in range(3):
            self.assertTrue(shaper.try_acquire("a").allowed)
        decision = shaper.try_acquire("a")
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "rate_limited")

    def test_refill_at_configured_rate(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=2, refill_rate=2.0, clock=clock
        )
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertFalse(shaper.try_acquire("a").allowed)
        clock.advance(0.5)  # 2 个/秒，半秒恰好补一个
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertFalse(shaper.try_acquire("a").allowed)

    def test_refill_is_capped_at_capacity(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=2, refill_rate=1.0, clock=clock
        )
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertTrue(shaper.try_acquire("a").allowed)
        clock.advance(100.0)  # 闲置再久也只能突发 capacity 个
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertFalse(shaper.try_acquire("a").allowed)

    def test_tenants_are_independent_without_global_bucket(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, clock=clock
        )
        self.assertTrue(shaper.try_acquire("a").allowed)
        self.assertFalse(shaper.try_acquire("a").allowed)
        self.assertTrue(shaper.try_acquire("b").allowed)

    def test_invalid_construction_arguments(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=0, refill_rate=1.0)
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=1, refill_rate=0.0)
        with self.assertRaises(ValueError):
            TokenBucketShaper(
                capacity=1, refill_rate=1.0, global_capacity=2
            )
        with self.assertRaises(ValueError):
            TokenBucketShaper(
                capacity=1, refill_rate=1.0, global_refill_rate=1.0
            )
        with self.assertRaises(ValueError):
            TokenBucketShaper(
                capacity=1, refill_rate=1.0, policy="drop"
            )
        with self.assertRaises(ValueError):
            TokenBucketShaper(
                capacity=1, refill_rate=1.0, max_wait=-1.0
            )


class TestFairness(unittest.TestCase):
    def _shaper(self, clock, policy=REJECT, max_wait=10.0):
        # 每租户速率 1/s、突发 2；全局速率 2/s 容得下两个满速租户。
        return TokenBucketShaper(
            capacity=2,
            refill_rate=1.0,
            global_capacity=4,
            global_refill_rate=2.0,
            policy=policy,
            max_wait=max_wait,
            clock=clock,
            sleep=advancing_sleep(clock),
        )

    def test_tenant_draining_its_bucket_cannot_starve_others(self):
        clock = ManualClock()
        shaper = self._shaper(clock)
        for _ in range(5):
            shaper.try_acquire("noisy")  # 突发 2 个后全被拒
        quiet = shaper.try_acquire("quiet")
        self.assertTrue(quiet.allowed)
        stats = shaper.stats()
        self.assertEqual(stats["allowed"], 3)
        self.assertEqual(stats["rejected"], 3)

    def test_global_bucket_enforces_shared_backend_quota(self):
        clock = ManualClock()
        shaper = self._shaper(clock)
        for _ in range(2):
            self.assertTrue(shaper.try_acquire("a").allowed)
        for _ in range(2):
            self.assertTrue(shaper.try_acquire("b").allowed)
        # 两边租户桶都还有全局额度兜底之外的余量已被共享桶用尽
        decision = shaper.try_acquire("a")
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "rate_limited")

    def test_refill_only_restores_abuser_rate_after_burst(self):
        clock = ManualClock()
        shaper = self._shaper(clock)
        shaper.try_acquire("noisy")
        shaper.try_acquire("noisy")
        shaper.try_acquire("quiet")
        clock.advance(1.0)  # noisy 补 1，quiet 桶满，全局补 2
        self.assertTrue(shaper.try_acquire("noisy").allowed)
        self.assertFalse(shaper.try_acquire("noisy").allowed)
        self.assertTrue(shaper.try_acquire("quiet").allowed)

    def test_queued_abuser_does_not_block_quiet_tenant(self):
        clock = ManualClock()
        shaper = self._shaper(clock, policy=QUEUE, max_wait=10.0)
        first = shaper.try_acquire("noisy")
        second = shaper.try_acquire("noisy")
        queued = shaper.try_acquire("noisy")
        self.assertEqual(queued.status, "queued")
        self.assertAlmostEqual(queued.ready_at, 1.0)
        # 排队中的 noisy 只预约自己速率下的未来令牌，quiet 当场可拿
        self.assertTrue(shaper.try_acquire("quiet").allowed)
        self.assertEqual(shaper.stats()["queued"], 1)
        shaper.wait(queued)  # 推进时钟到放行点
        self.assertEqual(queued.status, "allowed")
        self.assertAlmostEqual(queued.waited, 1.0)
        self.assertEqual(shaper.stats()["queued"], 0)
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)


class TestQueuePolicy(unittest.TestCase):
    def test_queueing_follows_refill_schedule(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1,
            refill_rate=1.0,
            policy=QUEUE,
            max_wait=10.0,
            clock=clock,
        )
        first = shaper.try_acquire("a")
        second = shaper.try_acquire("a")
        third = shaper.try_acquire("a")
        self.assertTrue(first.allowed)
        self.assertEqual(second.status, "queued")
        self.assertAlmostEqual(second.ready_at, 1.0)
        self.assertEqual(third.status, "queued")
        self.assertAlmostEqual(third.ready_at, 2.0)
        self.assertEqual(shaper.stats()["queued"], 2)

        clock.advance(0.999)
        shaper.stats()  # 触发结算但不应放行
        self.assertEqual(second.status, "queued")
        clock.advance(0.001)  # 恰好到达第一个补充点
        shaper.stats()
        self.assertEqual(second.status, "allowed")
        self.assertEqual(third.status, "queued")

    def test_wait_beyond_max_wait_is_rejected(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1,
            refill_rate=0.1,
            policy=QUEUE,
            max_wait=1.0,
            clock=clock,
        )
        self.assertTrue(shaper.try_acquire("a").allowed)
        decision = shaper.try_acquire("a")
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "wait_timeout")
        self.assertAlmostEqual(decision.ready_at, 10.0)
        self.assertEqual(shaper.stats()["queued"], 0)
        self.assertEqual(shaper.stats()["rejected"], 1)

    def test_acquire_blocks_until_token_is_ready(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1,
            refill_rate=2.0,
            policy=QUEUE,
            max_wait=10.0,
            clock=clock,
            sleep=advancing_sleep(clock),
        )
        self.assertTrue(shaper.acquire("a").allowed)
        decision = shaper.acquire("a")
        self.assertTrue(decision.allowed)
        self.assertAlmostEqual(decision.waited, 0.5)
        self.assertAlmostEqual(clock(), 0.5)
        self.assertEqual(shaper.stats()["queued"], 0)


class TestStats(unittest.TestCase):
    def test_stats_reports_tokens_rejections_and_queue(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=2,
            refill_rate=1.0,
            global_capacity=3,
            global_refill_rate=1.0,
            policy=QUEUE,
            max_wait=10.0,
            clock=clock,
        )
        shaper.try_acquire("a")
        shaper.try_acquire("a")
        shaper.try_acquire("b")
        queued = shaper.try_acquire("a")
        rejected = shaper.try_acquire("a")
        stats = shaper.stats()
        self.assertEqual(queued.status, "queued")
        self.assertEqual(rejected.status, "queued")
        self.assertAlmostEqual(stats["tokens"]["a"], 0.0)
        self.assertAlmostEqual(stats["tokens"]["b"], 1.0)
        self.assertAlmostEqual(stats["global_tokens"], 0.0)
        self.assertEqual(stats["queued"], 2)
        self.assertEqual(stats["allowed"], 3)
        self.assertEqual(stats["rejected"], 0)

        clock.advance(10.0)
        stats = shaper.stats()  # 排队请求全部到期放行，桶补满
        self.assertEqual(stats["queued"], 0)
        self.assertEqual(stats["allowed"], 5)
        self.assertAlmostEqual(stats["tokens"]["a"], 2.0)
        self.assertAlmostEqual(stats["tokens"]["b"], 2.0)
        self.assertAlmostEqual(stats["global_tokens"], 3.0)

    def test_stats_snapshot_is_independent(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0, clock=clock)
        shaper.try_acquire("a")
        snapshot = shaper.stats()
        snapshot["allowed"] = 99
        snapshot["tokens"]["a"] = 99
        self.assertEqual(shaper.stats()["allowed"], 1)
        self.assertAlmostEqual(shaper.stats()["tokens"]["a"], 0.0)

    def test_stats_without_global_bucket_reports_none(self):
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0)
        self.assertIsNone(shaper.stats()["global_tokens"])


if __name__ == "__main__":
    unittest.main()
