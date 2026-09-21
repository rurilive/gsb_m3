"""Ledger 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from slotledger.ledger import Entry, Ledger, LinkDown


class BasicTest(unittest.TestCase):
    def test_grant_returns_granted_and_deducts(self):
        ledger = Ledger(total=100)
        self.assertEqual(ledger.grant("alpha", 30), 30)
        self.assertEqual(ledger.remaining(), 70)
        self.assertEqual(ledger.outstanding("alpha"), 30)

    def test_grant_clamps_to_remaining(self):
        ledger = Ledger(total=100)
        self.assertEqual(ledger.grant("alpha", 130), 100)
        self.assertEqual(ledger.remaining(), 0)

    def test_grant_when_dry_returns_zero(self):
        ledger = Ledger(total=10)
        ledger.grant("alpha", 10)
        self.assertEqual(ledger.grant("beta", 5), 0)
        self.assertEqual(ledger.outstanding("beta"), 0)

    def test_grant_amount_must_be_positive_int(self):
        ledger = Ledger(total=10)
        with self.assertRaises(TypeError):
            ledger.grant("alpha", 1.5)
        with self.assertRaises(ValueError):
            ledger.grant("alpha", 0)
        with self.assertRaises(ValueError):
            ledger.grant("alpha", -3)

    def test_total_is_fixed(self):
        self.assertEqual(Ledger(total=42).total(), 42)

    def test_retire_restores_remaining(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 40)
        self.assertEqual(ledger.retire("alpha", 15), 15)
        self.assertEqual(ledger.remaining(), 75)
        self.assertEqual(ledger.outstanding("alpha"), 25)

    def test_retire_clamps_to_outstanding(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 30)
        self.assertEqual(ledger.retire("alpha", 99), 30)
        self.assertEqual(ledger.outstanding("alpha"), 0)
        self.assertEqual(ledger.remaining(), 100)

    def test_retire_unknown_site_returns_zero(self):
        ledger = Ledger(total=100)
        self.assertEqual(ledger.retire("ghost", 5), 0)
        self.assertEqual(ledger.remaining(), 100)

    def test_retire_amount_must_be_positive_int(self):
        ledger = Ledger(total=10)
        with self.assertRaises(TypeError):
            ledger.retire("alpha", 2.5)
        with self.assertRaises(ValueError):
            ledger.retire("alpha", 0)

    def test_outstanding_sums_all_sites(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 30)
        ledger.grant("beta", 20)
        self.assertEqual(ledger.outstanding(), 50)
        self.assertEqual(ledger.remaining() + ledger.outstanding(), ledger.total())

    def test_conservative_under_grant_retire_cycles(self):
        ledger = Ledger(total=60)
        for _ in range(5):
            ledger.grant("alpha", 25)
            ledger.retire("alpha", 10)
        self.assertEqual(ledger.remaining() + ledger.outstanding(), 60)
        self.assertEqual(ledger.outstanding("alpha"), 50)


class HistoryTest(unittest.TestCase):
    def test_seq_increments_and_kinds_recorded(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 30)
        ledger.retire("alpha", 10)
        ledger.grant("beta", 5)
        entries = ledger.history()
        self.assertEqual([entry.seq for entry in entries], [1, 2, 3])
        self.assertEqual([entry.kind for entry in entries],
                         ["grant", "retire", "grant"])
        self.assertEqual([entry.site for entry in entries],
                         ["alpha", "alpha", "beta"])
        self.assertEqual([entry.amount for entry in entries], [30, 10, 5])

    def test_failed_or_empty_ops_leave_no_entry(self):
        ledger = Ledger(total=5)
        ledger.grant("alpha", 5)
        self.assertEqual(ledger.grant("beta", 3), 0)
        self.assertEqual(len(ledger.history()), 1)

    def test_clock_is_injected(self):
        ticks = iter([5.0, 6.0, 7.0])
        ledger = Ledger(total=100, clock=lambda: next(ticks))
        ledger.grant("alpha", 1)
        ledger.grant("alpha", 1)
        ledger.retire("alpha", 1)
        self.assertEqual([entry.at for entry in ledger.history()], [5.0, 6.0, 7.0])

    def test_history_is_readonly_copy(self):
        ledger = Ledger(total=10)
        ledger.grant("alpha", 1)
        snapshot = ledger.history()
        ledger.grant("alpha", 1)
        self.assertEqual(len(snapshot), 1)
        self.assertIsInstance(snapshot[0], Entry)


class LinkTest(unittest.TestCase):
    def test_link_defaults_up(self):
        ledger = Ledger(total=10)
        self.assertTrue(ledger.link_up("alpha"))
        self.assertEqual(ledger.grant("alpha", 3), 3)

    def test_link_down_blocks_grant_and_retire(self):
        ledger = Ledger(total=10)
        ledger.grant("alpha", 4)
        ledger.set_link("alpha", False)
        with self.assertRaises(LinkDown):
            ledger.grant("alpha", 1)
        with self.assertRaises(LinkDown):
            ledger.retire("alpha", 1)
        self.assertEqual(ledger.remaining(), 6)
        self.assertEqual(ledger.outstanding("alpha"), 4)

    def test_restore_allows_ops_again(self):
        ledger = Ledger(total=10)
        ledger.set_link("alpha", False)
        ledger.set_link("alpha", True)
        self.assertEqual(ledger.grant("alpha", 2), 2)

    def test_other_site_unaffected_by_partition(self):
        ledger = Ledger(total=10)
        ledger.set_link("alpha", False)
        self.assertTrue(ledger.link_up("beta"))
        self.assertEqual(ledger.grant("beta", 2), 2)


class ConcurrencyTest(unittest.TestCase):
    def test_grant_race_never_oversues(self):
        total = 400
        ledger = Ledger(total=total)
        got = []
        lock = threading.Lock()

        def drain():
            while True:
                n = ledger.grant("alpha", 1)
                if not n:
                    break
                with lock:
                    got.append(n)

        workers = [threading.Thread(target=drain) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(got), total)
        self.assertEqual(len(got), total)
        self.assertEqual(ledger.remaining(), 0)

    def test_grant_and_retire_race_keeps_books_balanced(self):
        ledger = Ledger(total=100)

        def churn():
            for _ in range(200):
                ledger.grant("alpha", 7)
                ledger.retire("alpha", 7)

        workers = [threading.Thread(target=churn) for _ in range(6)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(ledger.remaining() + ledger.outstanding(), 100)
        self.assertLessEqual(ledger.outstanding("alpha"), 42)


if __name__ == "__main__":
    unittest.main()
