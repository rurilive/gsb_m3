"""BufferSite 预领批量行为的测试：假时钟假链路，不真 sleep。"""

import threading
import unittest

from slotledger.bench import round_trips
from slotledger.buffer import BufferSite
from slotledger.ledger import Ledger, LinkDown
from slotledger.plan import ideal_admissions, make_script, playout


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def buffer_site(ledger, name):
    return BufferSite(ledger, name)


class BatchTest(unittest.TestCase):
    def test_admit_draws_a_batch_per_trip(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        self.assertEqual(site.admit(3), 3)
        grants = [entry for entry in ledger.history() if entry.kind == "grant"]
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].amount, 8)
        self.assertEqual(site.in_hand(), 5)
        self.assertEqual(site.released(), 3)

    def test_refill_only_when_batch_empty(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(8)
        grants = [e for e in ledger.history() if e.kind == "grant"]
        self.assertEqual(len(grants), 1)
        site.admit(1)
        grants = [e for e in ledger.history() if e.kind == "grant"]
        self.assertEqual(len(grants), 2)
        self.assertEqual(site.released(), 9)

    def test_steady_state_at_most_one_trip_per_eight(self):
        clock = FakeClock()
        ledger = Ledger(total=10 ** 6)
        site = BufferSite(ledger, "alpha", clock=clock)
        for _ in range(20000):
            site.admit(1)
            clock.advance(0.001)
        self.assertEqual(site.released(), 20000)
        self.assertLessEqual(round_trips(ledger) * 8, site.released())

    def test_batch_grows_when_consumption_fast(self):
        clock = FakeClock()
        ledger = Ledger(total=10 ** 6)
        site = BufferSite(ledger, "alpha", clock=clock)
        seen = set()
        for _ in range(20):
            site.admit(site.batch_size())
            seen.add(site.batch_size())
        self.assertEqual(site.batch_size(), 4096)
        self.assertIn(8, seen)
        self.assertIn(16, seen)

    def test_batch_shrinks_when_consumption_slow(self):
        clock = FakeClock()
        ledger = Ledger(total=10 ** 6)
        site = BufferSite(ledger, "alpha", window=1.0, clock=clock)
        for _ in range(6):
            site.admit(site.batch_size())
        self.assertGreater(site.batch_size(), 8)
        for _ in range(6):
            clock.advance(100.0)
            site.admit(site.batch_size())
        self.assertEqual(site.batch_size(), 8)

    def test_nonpositive_n_is_noop(self):
        ledger = Ledger(total=10)
        site = BufferSite(ledger, "alpha")
        self.assertEqual(site.admit(0), 0)
        self.assertEqual(site.admit(-2), 0)
        self.assertEqual(len(ledger.history()), 0)
        self.assertIsNone(site.blocked_last())

    def test_full_run_clears_block_reason(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        ledger.set_link("alpha", False)
        site.admit(1)
        self.assertEqual(site.blocked_last(), "link_down")
        ledger.set_link("alpha", True)
        self.assertEqual(site.admit(4), 4)
        self.assertIsNone(site.blocked_last())


class ExhaustionTest(unittest.TestCase):
    def test_pool_dry_reports_exhausted(self):
        ledger = Ledger(total=10)
        site = BufferSite(ledger, "alpha")
        self.assertEqual(site.admit(30), 10)
        self.assertEqual(site.blocked_last(), "exhausted")
        self.assertEqual(site.released(), 10)
        self.assertEqual(ledger.remaining(), 0)
        self.assertEqual(site.in_hand(), 0)

    def test_never_exceeds_quota_with_two_sites(self):
        script = make_script(31, quota=120, rounds=4, partitions=0)
        result = playout(script, buffer_site)
        total = sum(result.admitted.values())
        self.assertLessEqual(total, 120)
        ledger = result.ledger
        self.assertEqual(ledger.remaining() + ledger.outstanding(), ledger.total())

    def test_plenty_quota_matches_ideal_per_site(self):
        script = make_script(7, quota=10 ** 6, rounds=4, partitions=0)
        ideal = ideal_admissions(script)
        result = playout(script, buffer_site)
        self.assertEqual(result.admitted["alpha"], ideal.per_site["alpha"])
        self.assertEqual(result.admitted["beta"], ideal.per_site["beta"])
        self.assertEqual(sum(result.admitted.values()), ideal.total)


class LinkTest(unittest.TestCase):
    def test_link_down_spends_hand_then_blocks(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(2)
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(3), 3)
        self.assertIsNone(site.blocked_last())
        self.assertEqual(site.admit(10), 3)
        self.assertEqual(site.blocked_last(), "link_down")
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.released(), 8)
        trips_before = len(ledger.history())
        site.admit(1)
        self.assertEqual(len(ledger.history()), trips_before)

    def test_link_down_with_empty_hand_blocks_at_once(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(4), 0)
        self.assertEqual(site.blocked_last(), "link_down")
        self.assertEqual(len(ledger.history()), 0)

    def test_restore_reconciles_before_new_grant(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(3)
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(2), 2)
        ledger.set_link("alpha", True)
        self.assertEqual(site.admit(1), 1)
        kinds = [entry.kind for entry in ledger.history()]
        self.assertEqual(kinds, ["grant", "report", "grant"])
        self.assertEqual(ledger.used("alpha"), 5)
        site.close()
        self.assertEqual(ledger.outstanding("alpha"), 0)
        books = ledger.remaining() + ledger.outstanding() + ledger.used()
        self.assertEqual(books, ledger.total())

    def test_reconcile_reports_used_and_leftover(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(3)
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(2), 2)
        ledger.set_link("alpha", True)
        site.admit(1)
        self.assertEqual(ledger.used("alpha"), 5)
        reports = [e for e in ledger.history() if e.kind == "report"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].amount, 8)
        books = ledger.remaining() + ledger.outstanding() + ledger.used()
        self.assertEqual(books, ledger.total())

    def test_partition_playout_keeps_red_line(self):
        script = make_script(11, quota=300, rounds=4, partitions=2)
        ideal = ideal_admissions(script)
        result = playout(script, buffer_site)
        total = sum(result.admitted.values())
        self.assertLessEqual(total, ideal.total)
        self.assertLessEqual(total, script.quota)
        ledger = result.ledger
        books = ledger.remaining() + ledger.outstanding() + ledger.used()
        self.assertEqual(books, ledger.total())

    def test_partition_round_admits_from_hand(self):
        script = make_script(11, quota=10 ** 6, rounds=4, partitions=2)
        during_down = {}
        released_before = {}

        def watch(index, rnd, ledger, sites):
            for name in script.sites:
                before = released_before.get(name, 0)
                now = sites[name].released()
                released_before[name] = now
                if name in rnd.down:
                    during_down[(index, name)] = now - before

        result = playout(script, buffer_site, on_round=watch)
        self.assertTrue(during_down)
        self.assertGreater(sum(during_down.values()), 0)
        total = sum(result.admitted.values())
        self.assertLessEqual(total, ideal_admissions(script).total)


class ReportTest(unittest.TestCase):
    def test_report_dedupes_retransmission(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 10)
        self.assertTrue(ledger.report("alpha", 1, 6, 4))
        self.assertEqual(ledger.remaining(), 94)
        self.assertEqual(ledger.used("alpha"), 6)
        self.assertFalse(ledger.report("alpha", 1, 6, 4))
        self.assertEqual(ledger.remaining(), 94)
        self.assertEqual(ledger.used("alpha"), 6)
        self.assertEqual(ledger.outstanding("alpha"), 0)
        reports = [e for e in ledger.history() if e.kind == "report"]
        self.assertEqual(len(reports), 1)

    def test_report_mismatch_rejected(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 10)
        with self.assertRaises(ValueError):
            ledger.report("alpha", 1, 5, 4)
        self.assertEqual(ledger.outstanding("alpha"), 10)
        self.assertEqual(ledger.remaining(), 90)

    def test_report_link_down_moves_nothing(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 10)
        ledger.set_link("alpha", False)
        with self.assertRaises(LinkDown):
            ledger.report("alpha", 1, 6, 4)
        self.assertEqual(ledger.outstanding("alpha"), 10)
        self.assertEqual(ledger.remaining(), 90)

    def test_report_validates_arguments(self):
        ledger = Ledger(total=100)
        ledger.grant("alpha", 10)
        with self.assertRaises(ValueError):
            ledger.report("alpha", 0, 5, 5)
        with self.assertRaises(ValueError):
            ledger.report("alpha", 1, -1, 11)
        with self.assertRaises(TypeError):
            ledger.report("alpha", 1, 5.0, 5)


class CloseTest(unittest.TestCase):
    def test_close_returns_hoard_and_balances_books(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(3)
        self.assertEqual(site.close(), 5)
        self.assertEqual(site.in_hand(), 0)
        self.assertEqual(ledger.outstanding("alpha"), 0)
        self.assertEqual(ledger.used("alpha"), 3)
        books = ledger.remaining() + ledger.outstanding() + ledger.used()
        self.assertEqual(books, ledger.total())
        self.assertEqual(site.close(), 0)

    def test_close_after_link_down_raises_then_recovers(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.admit(3)
        ledger.set_link("alpha", False)
        with self.assertRaises(LinkDown):
            site.close()
        ledger.set_link("alpha", True)
        self.assertEqual(site.close(), 5)
        self.assertEqual(ledger.outstanding("alpha"), 0)

    def test_admit_after_close_refuses(self):
        ledger = Ledger(total=100)
        site = BufferSite(ledger, "alpha")
        site.close()
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.blocked_last(), "closed")


class ConcurrencyTest(unittest.TestCase):
    def test_parallel_admit_matches_pool_exactly(self):
        total = 800
        ledger = Ledger(total=total)
        site = BufferSite(ledger, "alpha")
        barrier = threading.Barrier(4)

        def work():
            barrier.wait()
            for _ in range(200):
                site.admit(1)

        workers = [threading.Thread(target=work) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(site.released(), total)
        self.assertEqual(ledger.remaining(), 0)
        self.assertEqual(site.in_hand(), 0)
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.blocked_last(), "exhausted")

    def test_parallel_admit_no_loss_no_dup(self):
        total = 4000
        ledger = Ledger(total=total)
        site = BufferSite(ledger, "alpha")
        box = []
        lock = threading.Lock()

        def work():
            got = 0
            while True:
                n = site.admit(7)
                if n == 0:
                    break
                got += n
            with lock:
                box.append(got)

        workers = [threading.Thread(target=work) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(box), total)
        self.assertEqual(site.released(), total)
        self.assertEqual(ledger.remaining() + ledger.outstanding(), total)


if __name__ == "__main__":
    unittest.main()
