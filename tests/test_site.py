"""Site 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from slotledger.ledger import Ledger
from slotledger.site import Site


class AdmitTest(unittest.TestCase):
    def test_admit_grants_one_by_one(self):
        ledger = Ledger(total=100)
        site = Site(ledger, "alpha")
        self.assertEqual(site.admit(3), 3)
        grants = [entry for entry in ledger.history() if entry.kind == "grant"]
        self.assertEqual(len(grants), 3)
        self.assertTrue(all(entry.amount == 1 for entry in grants))

    def test_admit_default_is_one(self):
        ledger = Ledger(total=10)
        site = Site(ledger, "alpha")
        self.assertEqual(site.admit(), 1)
        self.assertEqual(site.released(), 1)

    def test_admit_full_run_clears_block_reason(self):
        ledger = Ledger(total=100)
        site = Site(ledger, "alpha")
        site.admit(4)
        self.assertIsNone(site.blocked_last())

    def test_admit_stops_when_pool_dry(self):
        ledger = Ledger(total=5)
        site = Site(ledger, "alpha")
        self.assertEqual(site.admit(8), 5)
        self.assertEqual(site.blocked_last(), "exhausted")
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.released(), 5)

    def test_dry_then_refill_resumes(self):
        ledger = Ledger(total=5)
        site = Site(ledger, "alpha")
        site.admit(5)
        ledger.retire("alpha", 2)
        self.assertEqual(site.admit(2), 2)
        self.assertIsNone(site.blocked_last())

    def test_nonpositive_n_is_noop(self):
        ledger = Ledger(total=10)
        site = Site(ledger, "alpha")
        self.assertEqual(site.admit(0), 0)
        self.assertEqual(site.admit(-2), 0)
        self.assertEqual(len(ledger.history()), 0)
        self.assertIsNone(site.blocked_last())

    def test_released_accumulates(self):
        ledger = Ledger(total=100)
        site = Site(ledger, "alpha")
        site.admit(3)
        site.admit(2)
        site.admit(7)
        self.assertEqual(site.released(), 12)

    def test_in_hand_is_always_zero(self):
        ledger = Ledger(total=10)
        site = Site(ledger, "alpha")
        site.admit(4)
        self.assertEqual(site.in_hand(), 0)


class LinkTest(unittest.TestCase):
    def test_link_down_blocks_admission(self):
        ledger = Ledger(total=100)
        site = Site(ledger, "alpha")
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(4), 0)
        self.assertEqual(site.blocked_last(), "link_down")
        self.assertEqual(site.released(), 0)
        self.assertEqual(len(ledger.history()), 0)

    def test_restore_resumes_admission(self):
        ledger = Ledger(total=100)
        site = Site(ledger, "alpha")
        ledger.set_link("alpha", False)
        site.admit(4)
        ledger.set_link("alpha", True)
        self.assertEqual(site.admit(4), 4)


class ConcurrencyTest(unittest.TestCase):
    def test_parallel_admit_matches_pool_exactly(self):
        total = 800
        ledger = Ledger(total=total)
        site = Site(ledger, "alpha")
        barrier = threading.Barrier(4)

        def work():
            barrier.wait()
            site.admit(200)

        workers = [threading.Thread(target=work) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(site.released(), total)
        self.assertEqual(ledger.remaining(), 0)
        self.assertIsNone(site.blocked_last())
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.blocked_last(), "exhausted")

    def test_parallel_admit_truncates_together(self):
        ledger = Ledger(total=50)
        site = Site(ledger, "alpha")
        box = []
        lock = threading.Lock()

        def work():
            got = site.admit(30)
            with lock:
                box.append(got)

        workers = [threading.Thread(target=work) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(box), 50)
        self.assertEqual(site.released(), 50)
        self.assertLess(len([n for n in box if n < 30]), 4)


if __name__ == "__main__":
    unittest.main()
