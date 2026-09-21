"""LockCounter 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from shardcount.counter import CounterStats, LockCounter
from shardcount.reference import drive, expected_totals, make_plan


class BasicTest(unittest.TestCase):
    def test_incr_returns_new_value(self):
        counter = LockCounter()
        self.assertEqual(counter.incr("a"), 1)
        self.assertEqual(counter.incr("a"), 2)
        self.assertEqual(counter.incr("a", 5), 7)

    def test_get_missing_key_is_zero(self):
        self.assertEqual(LockCounter().get("ghost"), 0)

    def test_negative_delta_allowed(self):
        counter = LockCounter()
        counter.incr("a", 3)
        self.assertEqual(counter.incr("a", -1), 2)
        self.assertEqual(counter.get("a"), 2)

    def test_zero_delta_leaves_key_hidden_and_total_unchanged(self):
        counter = LockCounter()
        self.assertEqual(counter.incr("a", 0), 0)
        self.assertEqual(counter.get("a"), 0)
        self.assertEqual(counter.keys(), [])

    def test_delta_must_be_int(self):
        with self.assertRaises(TypeError):
            LockCounter().incr("a", 1.5)

    def test_keys_lists_nonzero_keys_sorted(self):
        counter = LockCounter()
        counter.incr("b")
        counter.incr("a", 2)
        counter.incr("c")
        counter.incr("c", -1)
        self.assertEqual(counter.keys(), ["a", "b"])

    def test_total_sums_all_keys(self):
        counter = LockCounter()
        counter.incr("a", 2)
        counter.incr("b", -5)
        self.assertEqual(counter.total(), -3)

    def test_snapshot_returns_value_and_zeroes_key(self):
        counter = LockCounter()
        counter.incr("q", 4)
        self.assertEqual(counter.snapshot("q"), 4)
        self.assertEqual(counter.get("q"), 0)
        self.assertEqual(counter.keys(), [])

    def test_snapshot_missing_key_is_zero(self):
        self.assertEqual(LockCounter().snapshot("ghost"), 0)

    def test_snapshot_then_incr_starts_over(self):
        counter = LockCounter()
        counter.incr("q", 4)
        counter.snapshot("q")
        self.assertEqual(counter.incr("q", 2), 2)

    def test_stats_counts_operations(self):
        counter = LockCounter()
        counter.incr("a")
        counter.incr("a")
        counter.incr("b")
        counter.snapshot("a")
        stats = counter.stats()
        self.assertIsInstance(stats, CounterStats)
        self.assertEqual(stats.incrs, 3)
        self.assertEqual(stats.snapshots, 1)
        self.assertEqual(stats.keys, 1)

    def test_clock_is_injected(self):
        counter = LockCounter(clock=lambda: 12.5)
        counter.incr("a")
        self.assertEqual(counter.stats().last_change, 12.5)


class ConcurrencyTest(unittest.TestCase):
    def test_parallel_incr_matches_arithmetic_reference(self):
        plan = make_plan(seed=3, keys=("hot", "warm"), threads=4, per_thread=1000)
        counter = LockCounter()
        drive(counter, plan, barrier=threading.Barrier(len(plan)))
        self.assertEqual({k: counter.get(k) for k in counter.keys()}, expected_totals(plan))

    def test_snapshot_conserves_total_under_concurrency(self):
        plan = make_plan(seed=11, keys=("hot",), threads=4, per_thread=1500)
        expected = expected_totals(plan)["hot"]
        counter = LockCounter()
        taken = []
        stop = threading.Event()

        def snap_loop():
            while not stop.is_set():
                taken.append(counter.snapshot("hot"))

        snapper = threading.Thread(target=snap_loop)
        snapper.start()
        try:
            drive(counter, plan, barrier=threading.Barrier(len(plan)))
        finally:
            stop.set()
            snapper.join()
        self.assertEqual(sum(taken) + counter.get("hot"), expected)
        self.assertGreater(len(taken), 0)


if __name__ == "__main__":
    unittest.main()
