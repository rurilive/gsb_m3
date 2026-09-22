"""QuotaManager 行为基线：注册、申请、归还、幂等重放与流水。"""

import unittest

from quotatree import Ledger, QuotaManager, UnknownTeam


class RegisterTest(unittest.TestCase):
    def setUp(self):
        self.qm = QuotaManager()

    def test_register_and_read_back(self):
        self.qm.register("web", 100)
        self.qm.register("db", 40)
        self.assertEqual(self.qm.teams(), ["db", "web"])
        self.assertEqual(self.qm.limit("web"), 100)
        self.assertEqual(self.qm.available("web"), 100)
        self.assertEqual(self.qm.used("web"), 0)

    def test_duplicate_register_raises(self):
        self.qm.register("web", 100)
        with self.assertRaises(ValueError):
            self.qm.register("web", 50)

    def test_bad_team_names_rejected(self):
        for bad in ("", None, 7, ()):
            with self.assertRaises(ValueError):
                self.qm.register(bad, 10)

    def test_bad_limits_rejected(self):
        for bad in (0, -1, 2.5, True, "10", None):
            with self.assertRaises(ValueError):
                self.qm.register("ops", bad)
        self.assertEqual(self.qm.teams(), [])

    def test_unknown_team_raises(self):
        for call in (self.qm.acquire, self.qm.release):
            with self.assertRaises(UnknownTeam):
                call("nope", 1)
        for call in (self.qm.available, self.qm.used, self.qm.limit):
            with self.assertRaises(UnknownTeam):
                call("nope")


class AcquireReleaseTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.qm = QuotaManager(self.ledger)
        self.qm.register("web", 100)
        self.qm.register("db", 40)

    def test_acquire_within_limit(self):
        self.assertTrue(self.qm.acquire("web", 30))
        self.assertEqual(self.qm.used("web"), 30)
        self.assertEqual(self.qm.available("web"), 70)

    def test_acquire_exact_limit_then_reject(self):
        self.assertTrue(self.qm.acquire("web", 100))
        self.assertEqual(self.qm.available("web"), 0)
        self.assertFalse(self.qm.acquire("web", 1))
        self.assertEqual(self.qm.used("web"), 100)

    def test_rejected_acquire_changes_nothing(self):
        self.assertFalse(self.qm.acquire("db", 41))
        self.assertEqual(self.qm.used("db"), 0)
        self.assertEqual(self.qm.available("db"), 40)

    def test_release_returns_quota(self):
        self.qm.acquire("web", 80)
        self.assertTrue(self.qm.release("web", 30))
        self.assertEqual(self.qm.used("web"), 50)
        self.assertEqual(self.qm.available("web"), 50)

    def test_release_over_used_raises(self):
        self.qm.acquire("web", 10)
        with self.assertRaises(ValueError):
            self.qm.release("web", 11)
        self.assertEqual(self.qm.used("web"), 10)

    def test_bad_amounts_rejected(self):
        for bad in (0, -3, 1.5, True, None, "5"):
            with self.assertRaises(ValueError):
                self.qm.acquire("web", bad)
            with self.assertRaises(ValueError):
                self.qm.release("web", bad)

    def test_teams_are_independent(self):
        self.qm.acquire("web", 100)
        self.assertTrue(self.qm.acquire("db", 40))
        self.assertEqual(self.qm.available("web"), 0)
        self.assertEqual(self.qm.available("db"), 0)


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.qm = QuotaManager(self.ledger)
        self.qm.register("web", 100)
        self.qm.register("db", 40)

    def test_same_req_id_charges_once(self):
        self.assertTrue(self.qm.acquire("web", 60, req_id="r1"))
        self.assertTrue(self.qm.acquire("web", 60, req_id="r1"))
        self.assertEqual(self.qm.used("web"), 60)
        kinds = [e["kind"] for e in self.ledger.by_team("web")]
        self.assertEqual(kinds, ["acquire", "replay"])

    def test_repeated_release_does_not_over_credit(self):
        self.qm.acquire("web", 60, req_id="r1")
        self.qm.release("web", 60, req_id="r2")
        self.qm.release("web", 60, req_id="r2")
        self.assertEqual(self.qm.used("web"), 0)
        self.assertEqual(self.qm.available("web"), 100)

    def test_failed_acquire_replay_stays_failed(self):
        self.assertFalse(self.qm.acquire("db", 90, req_id="r3"))
        self.qm.acquire("db", 40)
        self.qm.release("db", 40)
        self.assertFalse(self.qm.acquire("db", 90, req_id="r3"))
        self.assertEqual(self.qm.used("db"), 0)

    def test_reused_req_id_with_other_params_raises(self):
        self.qm.acquire("web", 10, req_id="r4")
        with self.assertRaises(ValueError):
            self.qm.acquire("web", 20, req_id="r4")
        with self.assertRaises(ValueError):
            self.qm.acquire("db", 10, req_id="r4")
        with self.assertRaises(ValueError):
            self.qm.release("web", 10, req_id="r4")
        self.assertEqual(self.qm.used("web"), 10)

    def test_rejected_release_does_not_burn_req_id(self):
        self.qm.acquire("web", 10)
        with self.assertRaises(ValueError):
            self.qm.release("web", 20, req_id="r9")
        self.assertTrue(self.qm.release("web", 10, req_id="r9"))
        self.assertEqual(self.qm.used("web"), 0)

    def test_no_req_id_means_no_dedup(self):
        self.qm.acquire("web", 30)
        self.qm.acquire("web", 30)
        self.assertEqual(self.qm.used("web"), 60)


class LedgerWiringTest(unittest.TestCase):
    def test_attempts_are_recorded_in_order(self):
        ledger = Ledger()
        qm = QuotaManager(ledger)
        qm.register("web", 100)
        qm.acquire("web", 30, req_id="a1")
        qm.acquire("web", 90, req_id="a2")
        qm.release("web", 10, req_id="a3")
        entries = ledger.entries()
        self.assertEqual(
            [(e["seq"], e["kind"], e["amount"], e["ok"]) for e in entries],
            [(1, "acquire", 30, True),
             (2, "acquire", 90, False),
             (3, "release", 10, True)])
        stats = ledger.stats()
        self.assertEqual(stats["acquire"], 2)
        self.assertEqual(stats["release"], 1)
        self.assertEqual(stats["replay"], 0)
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(ledger.count(), 3)

    def test_manager_makes_own_ledger(self):
        qm = QuotaManager()
        self.assertIsInstance(qm.ledger, Ledger)


if __name__ == "__main__":
    unittest.main()
