"""续期、回收与看护对象的新行为测试。

全程用手动假时钟，不起任何真实线程、不碰真实时间。
"""

import unittest

from leasekit.lease import LeaseManager, LeaseWatchdog


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
    def test_renew_pushes_expiry_back(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        clock.advance(20.0)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        self.assertEqual(m.get(lease_id).expires_at, 20.0 + 30.0)
        self.assertEqual(m.get(lease_id).ttl, 30.0)

    def test_renew_uses_now_plus_ttl_not_old_expiry(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        clock.advance(1.0)
        m.renew(lease_id, "worker-1")
        # 旧到期点是 30，续期后必须是 1 + 30 = 31，而不是 60。
        self.assertEqual(m.get(lease_id).expires_at, 31.0)

    def test_renew_keeps_original_ttl_by_default(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        m.renew(lease_id, "worker-1")
        lease = m.get(lease_id)
        self.assertEqual(lease.ttl, 10.0)
        self.assertEqual(lease.expires_at, 15.0)

    def test_renew_with_explicit_ttl_becomes_new_default(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1", ttl=10.0)
        clock.advance(5.0)
        m.renew(lease_id, "worker-1", ttl=40.0)
        lease = m.get(lease_id)
        self.assertEqual(lease.ttl, 40.0)
        self.assertEqual(lease.expires_at, 45.0)
        clock.advance(39.0)                     # 44s，还差 1s 到期
        m.renew(lease_id, "worker-1")
        self.assertEqual(m.get(lease_id).ttl, 40.0)
        self.assertEqual(m.get(lease_id).expires_at, 84.0)

    def test_renew_returns_true(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        self.assertIs(m.renew(lease_id, "worker-1"), True)

    def test_renew_by_wrong_holder_is_false_and_untouched(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(5.0)
        self.assertFalse(m.renew(lease_id, "worker-2"))
        lease = m.get(lease_id)
        self.assertEqual(lease.holder, "worker-1")
        self.assertEqual(lease.ttl, 10.0)
        self.assertEqual(lease.expires_at, 10.0)   # 到期点纹丝没动

    def test_renew_after_expiry_is_false_and_untouched(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(10.0)
        self.assertFalse(m.renew(lease_id, "worker-1"))
        self.assertIsNone(m.get(lease_id))

    def test_renew_unknown_lease_is_false(self):
        m = LeaseManager(clock=FakeClock())
        self.assertFalse(m.renew("no-such-lease", "worker-1"))

    def test_renew_invalid_ttl_raises_and_untouched(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        with self.assertRaises(ValueError):
            m.renew(lease_id, "worker-1", ttl=0)
        with self.assertRaises(ValueError):
            m.renew(lease_id, "worker-1", ttl=-5.0)
        self.assertEqual(m.get(lease_id).expires_at, 10.0)

    def test_renew_when_expires_exactly_at_boundary_fails(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(9.999)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        clock.advance(10.0)                      # 恰好踩在到期点上
        self.assertFalse(m.renew(lease_id, "worker-1"))

    def test_renew_does_not_change_granted_count(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        m.renew(lease_id, "worker-1")
        m.renew(lease_id, "worker-1")
        self.assertEqual(m.stats()["granted"], 1)


class TestReap(unittest.TestCase):
    def test_reap_removes_expired_and_returns_ids(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        a = m.acquire("worker-1")
        b = m.acquire("worker-2")
        c = m.acquire("worker-3")
        clock.advance(11.0)
        reaped = m.reap_expired()
        self.assertEqual(sorted(reaped), sorted([a, b, c]))
        self.assertEqual(m.stats()["live"], 0)
        for lease_id in (a, b, c):
            self.assertIsNone(m.get(lease_id))

    def test_reap_keeps_live_and_renewed_leases(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        keep = m.acquire("worker-1", ttl=100.0)
        renewed = m.acquire("worker-2", ttl=10.0)
        stale = m.acquire("worker-3", ttl=10.0)
        clock.advance(9.0)
        m.renew(renewed, "worker-2")             # 到期点推到 19
        clock.advance(2.0)                       # 现在 11：stale 已死
        reaped = m.reap_expired()
        self.assertEqual(reaped, [stale])
        self.assertIsNotNone(m.get(keep))
        self.assertIsNotNone(m.get(renewed))

    def test_renew_then_immediate_reap_has_no_dead_window(self):
        # 续期与回收撞车的核心断言：同一时刻先续完再回收，
        # 刚续上的租约绝不能被清掉。
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(9.999)
        self.assertTrue(m.renew(lease_id, "worker-1"))
        self.assertEqual(m.reap_expired(), [])
        self.assertIsNotNone(m.get(lease_id))

    def test_reap_counts_in_stats_once(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        m.acquire("worker-1")
        m.acquire("worker-2")
        clock.advance(11.0)
        self.assertEqual(m.stats()["reaped"], 0)
        first = m.reap_expired()
        self.assertEqual(len(first), 2)
        self.assertEqual(m.stats()["reaped"], 2)
        self.assertEqual(m.reap_expired(), [])   # 再回收没有重复计数
        self.assertEqual(m.stats()["reaped"], 2)

    def test_reap_does_not_count_release(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        a = m.acquire("worker-1")
        m.acquire("worker-2")
        m.release(a, "worker-1")
        clock.advance(11.0)
        m.reap_expired()
        s = m.stats()
        self.assertEqual(s["released"], 1)
        self.assertEqual(s["reaped"], 1)

    def test_expiring_exactly_at_now_gets_reaped(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(10.0)
        self.assertEqual(m.reap_expired(), [lease_id])


class TestWatchdog(unittest.TestCase):
    def _collect(self):
        events = []
        return events, lambda lease_id, holder, reason: events.append(
            (lease_id, holder, reason))

    def test_tick_before_interval_does_nothing(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(9.999)
        self.assertFalse(wd.tick())
        self.assertEqual(events, [])
        self.assertEqual(m.get(lease_id).expires_at, 30.0)

    def test_tick_at_interval_renews_and_reschedules(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 10.0, on_lost)
        clock.advance(10.0)
        self.assertTrue(wd.tick())
        self.assertEqual(m.get(lease_id).expires_at, 40.0)
        clock.advance(10.0)
        self.assertTrue(wd.tick())
        self.assertEqual(m.get(lease_id).expires_at, 50.0)
        self.assertEqual(events, [])

    def test_watchdog_keeps_long_task_lease_alive_across_many_periods(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 10.0, on_lost)
        for _ in range(20):                     # 任务跑 200s，远超 30s TTL
            clock.advance(10.0)
            wd.tick()
        self.assertIsNotNone(m.get(lease_id))
        self.assertEqual(events, [])
        self.assertEqual(m.get(lease_id).expires_at, 230.0)

    def test_notified_when_lease_expired_between_ticks(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 30.0, on_lost)
        clock.advance(30.0)                     # 看护间隔比租期长
        self.assertFalse(wd.tick())
        self.assertEqual(events, [(lease_id, "worker-1", "gone")])
        self.assertTrue(wd.lost)

    def test_notified_when_reaped_before_tick(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 5.0, on_lost)
        clock.advance(11.0)
        m.reap_expired()
        wd.tick()
        self.assertEqual(events, [(lease_id, "worker-1", "gone")])

    def test_lost_watchdog_notifies_once_and_stays_idle(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 30.0, on_lost)
        clock.advance(30.0)
        wd.tick()
        clock.advance(30.0)
        self.assertFalse(wd.tick())
        self.assertEqual(len(events), 1)

    def test_watchdog_uses_given_ttl_for_renewal(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=100.0)
        lease_id = m.acquire("worker-1", ttl=100.0)
        events, on_lost = self._collect()
        wd = LeaseWatchdog(m, lease_id, "worker-1", 10.0, on_lost, ttl=5.0)
        clock.advance(10.0)
        wd.tick()
        self.assertEqual(m.get(lease_id).ttl, 5.0)
        self.assertEqual(m.get(lease_id).expires_at, 15.0)

    def test_invalid_interval_raises(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        with self.assertRaises(ValueError):
            LeaseWatchdog(m, lease_id, "worker-1", 0, lambda *a: None)


if __name__ == "__main__":
    unittest.main()
