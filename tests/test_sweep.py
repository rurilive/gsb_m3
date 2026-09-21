import unittest

from tokengate import KeyRing, ManualClock, TokenService


def make_service(refresh_ttl=100, skew=5, access_ttl=10):
    clock = ManualClock(10_000.0)
    return TokenService(KeyRing({"k1": "s"}), clock,
                        access_ttl=access_ttl, refresh_ttl=refresh_ttl,
                        skew=skew), clock


class SweepTests(unittest.TestCase):
    def test_nothing_is_collected_while_live(self):
        svc, clock = make_service(refresh_ttl=100, skew=5)
        pairs = [svc.issue() for _ in range(5)]
        clock.advance(100)  # refresh exp is at 10100; +skew 10105, not yet
        report = svc.sweep()
        self.assertEqual(report.sessions_removed, 0)
        self.assertEqual(report.sessions_remaining, 5)
        self.assertEqual(len(svc.store), 5)
        # Sessions live even though their short access strings expired;
        # their refresh tokens still rotate.
        for pair in pairs:
            rotated = svc.refresh(pair.refresh_token)
            self.assertEqual(rotated.sid, pair.sid)

    def test_expired_sessions_are_collected_only_past_skew(self):
        svc, clock = make_service(refresh_ttl=100, skew=5)
        pair = svc.issue()
        clock.set(10_104.0)  # 10000 + 100 + 5 - 1
        self.assertEqual(svc.sweep().sessions_removed, 0)
        clock.set(10_105.0)  # boundary itself is still live
        self.assertEqual(svc.sweep().sessions_removed, 0)
        clock.set(10_105.5)
        report = svc.sweep()
        self.assertEqual(report.sessions_removed, 1)
        self.assertEqual(report.sessions_remaining, 0)
        self.assertNotIn(pair.sid, svc.store)

    def test_sweep_mixes_ages(self):
        svc, clock = make_service(refresh_ttl=100, skew=0)
        old = svc.issue()
        clock.set(10_500.0)
        mid = svc.issue()
        clock.set(11_000.0)
        fresh = svc.issue()
        # old refresh exp 10100 (gone); mid exp 10600 (gone); fresh 11100
        report = svc.sweep()
        self.assertEqual(report.sessions_removed, 2)
        self.assertEqual(sorted(svc.store.sids()), [fresh.sid])
        self.assertNotIn(old.sid, svc.store)
        self.assertNotIn(mid.sid, svc.store)

    def test_revoked_tombstones_are_swept_too(self):
        svc, clock = make_service(refresh_ttl=100, skew=5)
        svc.revoke_session(svc.issue().sid)
        # bound = max(now + 100, refresh_exp 10100) + 5 = 10105
        clock.set(10_105.5)
        report = svc.sweep()
        self.assertEqual(report.sessions_removed, 0)
        self.assertEqual(report.revocations_removed, 1)
        self.assertEqual(report.revocations_remaining, 0)

    def test_table_does_not_grow_under_churn(self):
        svc, clock = make_service(refresh_ttl=100, skew=0)
        high_water = 0
        for step in range(400):
            svc.issue()
            if step % 5 == 0:
                svc.revoke_session(svc.store.sids()[0])
            clock.advance(7)
            svc.sweep()
            high_water = max(high_water, len(svc.store) + len(svc.revocations))
        # New sessions age out every 107 sim-seconds; at 7s per step the
        # live set plus tombstones must stay a small, bounded number.
        self.assertLess(high_water, 40)
        self.assertLess(len(svc.store) + len(svc.revocations), 40)

    def test_sweep_is_idempotent(self):
        svc, clock = make_service(refresh_ttl=10)
        svc.issue()
        clock.advance(1000)
        first = svc.sweep()
        second = svc.sweep()
        self.assertEqual(first.sessions_removed, 1)
        self.assertEqual(second.sessions_removed, 0)
        self.assertEqual(second.sessions_remaining, 0)


if __name__ == "__main__":
    unittest.main()
