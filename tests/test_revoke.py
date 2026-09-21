import unittest

from tokengate import ManualClock, RevocationList, UnknownSession


class RevocationListTests(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock(1000.0)
        self.rl = RevocationList(self.clock)

    def test_revoke_and_query_is_constant_time_shape(self):
        self.assertFalse(self.rl.is_revoked("s1"))
        self.rl.revoke("s1", 1500)
        self.assertTrue(self.rl.is_revoked("s1"))
        self.assertIn("s1", self.rl)
        self.assertEqual(len(self.rl), 1)

    def test_revoke_keeps_the_latest_bound(self):
        self.assertEqual(self.rl.revoke("s1", 1500), 1500)
        self.assertEqual(self.rl.revoke("s1", 1200), 1500)
        self.assertEqual(self.rl.expires_at("s1"), 1500)
        self.assertEqual(self.rl.revoke("s1", 1800), 1800)

    def test_expires_at_unknown_raises(self):
        with self.assertRaises(UnknownSession):
            self.rl.expires_at("ghost")

    def test_discard(self):
        self.rl.revoke("s1", 1500)
        self.assertTrue(self.rl.discard("s1"))
        self.assertFalse(self.rl.discard("s1"))

    def test_sids_sorted(self):
        for sid in ("b", "a", "c"):
            self.rl.revoke(sid, 2000)
        self.assertEqual(self.rl.sids(), ["a", "b", "c"])

    def test_sweep_drops_strictly_past_bound(self):
        self.rl.revoke("early", 1200)
        self.rl.revoke("on_the_line", 1300)
        self.rl.revoke("later", 1400)
        report = self.rl.sweep(now=1300)
        self.assertEqual(report, {"removed": 1, "remaining": 2})
        self.assertFalse(self.rl.is_revoked("early"))
        self.assertTrue(self.rl.is_revoked("on_the_line"))
        report = self.rl.sweep()  # clock is still at 1000
        self.assertEqual(report["removed"], 0)
        self.clock.set(1301)
        report = self.rl.sweep()
        self.assertEqual(report, {"removed": 1, "remaining": 1})

    def test_sweep_without_clock_or_now_raises(self):
        with self.assertRaises(RuntimeError):
            RevocationList().sweep()

    def test_bind_clock_enables_parameterless_sweep(self):
        rl = RevocationList()
        rl.revoke("s1", 1100)
        rl.bind_clock(self.clock)
        self.assertEqual(rl.sweep()["removed"], 0)
        self.clock.set(1101)
        self.assertEqual(rl.sweep()["removed"], 1)


if __name__ == "__main__":
    unittest.main()
