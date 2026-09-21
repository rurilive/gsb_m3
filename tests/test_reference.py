"""压测计划与纯算术参考的锁定测试，基线不许动。"""

import threading
import unittest

from shardcount.counter import LockCounter
from shardcount.reference import drive, expected_totals, make_plan


class PlanTest(unittest.TestCase):
    def test_same_seed_same_plan(self):
        self.assertEqual(
            make_plan(5, keys=("hot", "warm"), threads=3, per_thread=50),
            make_plan(5, keys=("hot", "warm"), threads=3, per_thread=50),
        )

    def test_different_seed_differs(self):
        self.assertNotEqual(
            make_plan(5, keys=("hot",), threads=3, per_thread=50),
            make_plan(6, keys=("hot",), threads=3, per_thread=50),
        )

    def test_plan_shape(self):
        plan = make_plan(1, threads=3, per_thread=20)
        self.assertEqual(len(plan), 3)
        self.assertTrue(all(len(part) == 20 for part in plan))

    def test_hot_key_dominates(self):
        plan = make_plan(2, keys=("hot", "cold"), threads=2, per_thread=500)
        counts = {}
        for part in plan:
            for key, _ in part:
                counts[key] = counts.get(key, 0) + 1
        self.assertGreater(counts["hot"], counts["cold"])

    def test_plan_contains_negative_and_zero_deltas(self):
        deltas = {delta for part in make_plan(4, threads=4, per_thread=500) for _, delta in part}
        self.assertIn(-1, deltas)
        self.assertIn(0, deltas)


class ReferenceTest(unittest.TestCase):
    def test_expected_totals_is_plain_arithmetic(self):
        plan = [[("a", 2), ("a", -1)], [("b", 3), ("a", 1)]]
        self.assertEqual(expected_totals(plan), {"a": 2, "b": 3})

    def test_drive_runs_every_op(self):
        plan = make_plan(9, keys=("hot", "warm", "cold"), threads=4, per_thread=800)
        counter = LockCounter()
        drive(counter, plan)
        self.assertEqual({k: counter.get(k) for k in counter.keys()}, expected_totals(plan))

    def test_drive_returns_joined_workers(self):
        plan = make_plan(9, threads=2, per_thread=10)
        workers = drive(LockCounter(), plan, barrier=threading.Barrier(len(plan)))
        self.assertEqual(len(workers), 2)
        self.assertTrue(all(not worker.is_alive() for worker in workers))


if __name__ == "__main__":
    unittest.main()
