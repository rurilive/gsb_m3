"""续期 / 回收 / 看护对象的新行为测试。

全程手动推进假时钟，不起任何真线程：主循环的节拍直接用 tick 模拟。
"""

import unittest

from leasekit.lease import LeaseManager, LeaseWatcher


class FakeClock:
    """手动推进的假时钟，测试里用来踩到期边界。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class TestRenew(unittest.TestCase):
    def test_renew_extends_expiry_using_original_ttl(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(8.0)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        self.assertEqual(m.get(lease_id).expires_at, 18.0)
        clock.advance(9.0)
        self.assertIsNotNone(m.get(lease_id))

    def test_renew_keeps_original_ttl_in_snapshot(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        m.renew(lease_id, "worker-1")
        self.assertEqual(m.get(lease_id).ttl, 10.0)

    def test_renew_with_explicit_ttl_overrides(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        self.assertTrue(m.renew(lease_id, "worker-1", ttl=20.0))
        lease = m.get(lease_id)
        self.assertEqual(lease.ttl, 20.0)
        self.assertEqual(lease.expires_at, 25.0)

    def test_explicit_ttl_is_used_for_following_default_renew(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        m.renew(lease_id, "worker-1", ttl=20.0)
        clock.advance(10.0)
        m.renew(lease_id, "worker-1")
        self.assertEqual(m.get(lease_id).expires_at, 35.0)

    def test_renew_can_chain_across_many_cycles(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        for _ in range(20):
            clock.advance(25.0)
            self.assertTrue(m.renew(lease_id, "worker-1"))
        self.assertEqual(m.get(lease_id).expires_at, 530.0)

    def test_renew_wrong_holder_is_refused_and_untouched(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        self.assertFalse(m.renew(lease_id, "worker-2"))
        lease = m.get(lease_id)
        self.assertEqual(lease.holder, "worker-1")
        self.assertEqual(lease.expires_at, 10.0)

    def test_renew_unknown_is_false(self):
        m = LeaseManager(clock=FakeClock())
        self.assertFalse(m.renew("no-such-lease", "worker-1"))

    def test_renew_after_expiry_is_false(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(10.0)
        self.assertFalse(m.renew(lease_id, "worker-1"))
        self.assertIsNone(m.get(lease_id))

    def test_renew_right_at_expiry_boundary_is_false(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(9.999)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        clock.advance(10.0)       # 恰好踩到续期后的 expires_at
        self.assertFalse(m.renew(lease_id, "worker-1"))

    def test_renew_invalid_ttl_raises_and_untouched(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=10.0)
        with self.assertRaises(ValueError):
            m.renew(lease_id, "worker-1", ttl=0)
        with self.assertRaises(ValueError):
            m.renew(lease_id, "worker-1", ttl=-1.0)
        self.assertEqual(m.get(lease_id).expires_at, 10.0)


class TestReap(unittest.TestCase):
    def test_reap_removes_only_expired_leases(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        gone1 = m.acquire("worker-2")
        gone2 = m.acquire("worker-3")
        clock.advance(5.0)
        keep = m.acquire("worker-1")
        clock.advance(9.9)
        self.assertEqual(m.reap_expired(), 2)
        self.assertIsNotNone(m.get(keep))
        self.assertIsNone(m.get(gone1))
        self.assertIsNone(m.get(gone2))

    def test_reap_empty_returns_zero(self):
        m = LeaseManager(clock=FakeClock())
        self.assertEqual(m.reap_expired(), 0)

    def test_reap_does_not_remove_live_or_released(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        handed = m.acquire("worker-2")
        clock.advance(5.0)
        active = m.acquire("worker-1")
        m.release(handed, "worker-2")
        clock.advance(5.0)
        self.assertEqual(m.reap_expired(), 0)
        self.assertIsNotNone(m.get(active))

    def test_reap_is_incremental(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        m.acquire("worker-1")
        clock.advance(10.0)
        self.assertEqual(m.reap_expired(), 1)
        m.acquire("worker-2")
        clock.advance(10.0)
        self.assertEqual(m.reap_expired(), 1)

    def test_reap_counts_in_stats(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        m.acquire("worker-1")
        m.acquire("worker-2")
        clock.advance(10.0)
        m.reap_expired()
        s = m.stats()
        self.assertEqual(s["reaped"], 2)
        self.assertEqual(s["live"], 0)
        self.assertEqual(s["granted"], 2)

    def test_reaped_lease_cannot_be_renewed(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(10.0)
        m.reap_expired()
        self.assertFalse(m.renew(lease_id, "worker-1"))


class TestRenewAndReapOrdering(unittest.TestCase):
    def test_renewed_lease_survives_reap_in_same_instant(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(9.0)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        # 同一时刻由主循环顺手回收：刚续上的租约绝不能被清掉
        self.assertEqual(m.reap_expired(), 0)
        self.assertIsNotNone(m.get(lease_id))
        self.assertEqual(m.stats()["reaped"], 0)

    def test_expired_lease_loses_renew_and_then_gets_reaped(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(10.0)
        self.assertFalse(m.renew(lease_id, "worker-1"))
        self.assertEqual(m.reap_expired(), 1)
        self.assertEqual(m.stats()["reaped"], 1)


class TestWatcher(unittest.TestCase):
    def _collector(self):
        events = []
        return events, lambda lease_id, holder: events.append((lease_id, holder))

    def test_watcher_renews_before_expiry_without_threads(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        for _ in range(5):
            clock.advance(10.0)
            watcher.tick()
        self.assertEqual(events, [])
        self.assertTrue(watcher.active)
        self.assertEqual(m.get(lease_id).expires_at, 80.0)

    def test_tick_before_interval_does_nothing(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(9.999)
        watcher.tick()
        self.assertEqual(m.get(lease_id).expires_at, 30.0)
        self.assertEqual(events, [])

    def test_watcher_catches_up_after_main_loop_stall(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(25.0)          # 主循环卡了 25s，但仍在 TTL 内
        watcher.tick()
        self.assertEqual(events, [])
        self.assertEqual(m.get(lease_id).expires_at, 55.0)

    def test_watcher_notifies_immediately_when_renew_fails(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(30.0)          # 主循环卡住跨过 TTL，租约已作废
        watcher.tick()
        self.assertEqual(events, [(lease_id, "worker-1")])
        self.assertFalse(watcher.active)

    def test_watcher_notifies_when_lease_was_reaped(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(30.0)
        m.reap_expired()
        watcher.tick()
        self.assertEqual(events, [(lease_id, "worker-1")])
        self.assertFalse(watcher.active)

    def test_watcher_notifies_only_once_then_goes_quiet(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(30.0)
        watcher.tick()
        watcher.tick()
        clock.advance(100.0)
        watcher.tick()
        self.assertEqual(events, [(lease_id, "worker-1")])

    def test_stop_ends_watch_without_loss_notification(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 10.0, on_lost)
        watcher.stop()
        clock.advance(40.0)
        watcher.tick()
        self.assertFalse(watcher.active)
        self.assertEqual(events, [])

    def test_watcher_renews_with_explicit_ttl(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock)
        lease_id = m.acquire("worker-1", ttl=30.0)
        events, on_lost = self._collector()
        watcher = LeaseWatcher(m, lease_id, "worker-1", 5.0, on_lost, ttl=8.0)
        clock.advance(5.0)
        watcher.tick()
        lease = m.get(lease_id)
        self.assertEqual(lease.ttl, 8.0)
        self.assertEqual(lease.expires_at, 13.0)

    def test_watcher_requires_live_lease_held_by_holder(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        with self.assertRaises(ValueError):
            LeaseWatcher(m, lease_id, "worker-2", 10.0, lambda *a: None)
        with self.assertRaises(ValueError):
            LeaseWatcher(m, "missing", "worker-1", 10.0, lambda *a: None)

    def test_watcher_rejects_non_positive_interval(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        with self.assertRaises(ValueError):
            LeaseWatcher(m, lease_id, "worker-1", 0, lambda *a: None)


if __name__ == "__main__":
    unittest.main()
