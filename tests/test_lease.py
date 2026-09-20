"""LeaseManager 现有行为的锁定测试。

这些断言描述的是改造之前就成立的行为，一个字都不许动。
"""

import unittest

from leasekit.lease import Lease, LeaseManager


class FakeClock:
    """手动推进的假时钟，测试里用来踩到期边界。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class TestAcquireAndGet(unittest.TestCase):
    def test_acquire_then_get(self):
        m = LeaseManager(clock=FakeClock(), default_ttl=30.0)
        lease_id = m.acquire("worker-1")
        lease = m.get(lease_id)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.id, lease_id)
        self.assertEqual(lease.holder, "worker-1")
        self.assertEqual(lease.ttl, 30.0)
        self.assertEqual(lease.expires_at, 30.0)

    def test_get_unknown_returns_none(self):
        m = LeaseManager(clock=FakeClock())
        self.assertIsNone(m.get("no-such-lease"))

    def test_explicit_ttl_overrides_default(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=30.0)
        lease_id = m.acquire("worker-1", ttl=5.0)
        self.assertEqual(m.get(lease_id).ttl, 5.0)
        self.assertEqual(m.get(lease_id).expires_at, 5.0)

    def test_get_expired_returns_none(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(9.999)
        self.assertIsNotNone(m.get(lease_id))
        clock.advance(0.001)          # 恰好踩到 expires_at
        self.assertIsNone(m.get(lease_id))

    def test_get_returns_snapshot_not_internal_state(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        first = m.get(lease_id)
        second = m.get(lease_id)
        self.assertIsNot(first, second)
        self.assertEqual(first, second)

    def test_lease_ids_are_unique(self):
        m = LeaseManager(clock=FakeClock())
        ids = {m.acquire("worker-1") for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_same_holder_can_hold_several_leases(self):
        m = LeaseManager(clock=FakeClock())
        a = m.acquire("worker-1")
        b = m.acquire("worker-1")
        self.assertNotEqual(a, b)
        self.assertIsNotNone(m.get(a))
        self.assertIsNotNone(m.get(b))

    def test_invalid_ttl_raises(self):
        m = LeaseManager(clock=FakeClock())
        with self.assertRaises(ValueError):
            m.acquire("worker-1", ttl=0)
        with self.assertRaises(ValueError):
            m.acquire("worker-1", ttl=-1.0)

    def test_invalid_default_ttl_raises(self):
        with self.assertRaises(ValueError):
            LeaseManager(clock=FakeClock(), default_ttl=0)


class TestRelease(unittest.TestCase):
    def test_holder_can_release(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        self.assertTrue(m.release(lease_id, "worker-1"))
        self.assertIsNone(m.get(lease_id))

    def test_release_is_not_idempotent(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        self.assertTrue(m.release(lease_id, "worker-1"))
        self.assertFalse(m.release(lease_id, "worker-1"))

    def test_release_by_wrong_holder_is_refused(self):
        m = LeaseManager(clock=FakeClock())
        lease_id = m.acquire("worker-1")
        self.assertFalse(m.release(lease_id, "worker-2"))
        self.assertIsNotNone(m.get(lease_id))   # 租约没被动过

    def test_release_unknown_is_false(self):
        m = LeaseManager(clock=FakeClock())
        self.assertFalse(m.release("no-such-lease", "worker-1"))

    def test_release_after_expiry_is_false(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        lease_id = m.acquire("worker-1")
        clock.advance(11.0)
        self.assertFalse(m.release(lease_id, "worker-1"))


class TestStats(unittest.TestCase):
    def test_stats_counts(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        a = m.acquire("worker-1")
        m.acquire("worker-2")
        m.release(a, "worker-1")
        s = m.stats()
        self.assertEqual(s["granted"], 2)
        self.assertEqual(s["released"], 1)
        self.assertEqual(s["live"], 1)

    def test_live_excludes_expired_but_undeleted(self):
        clock = FakeClock()
        m = LeaseManager(clock=clock, default_ttl=10.0)
        m.acquire("worker-1")
        m.acquire("worker-2")
        clock.advance(11.0)
        self.assertEqual(m.stats()["live"], 0)

    def test_stats_returns_fresh_dict(self):
        m = LeaseManager(clock=FakeClock())
        s = m.stats()
        s["granted"] = 99
        self.assertEqual(m.stats()["granted"], 0)

    def test_lease_is_frozen_snapshot(self):
        m = LeaseManager(clock=FakeClock())
        lease = m.get(m.acquire("worker-1"))
        self.assertIsInstance(lease, Lease)
        with self.assertRaises(Exception):
            lease.expires_at = 12345.0


if __name__ == "__main__":
    unittest.main()
