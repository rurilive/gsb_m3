"""ShardedCounter 的行为测试：单线程语义对齐 LockCounter，多线程对拍。"""

import threading
import unittest

from shardcount.counter import CounterStats, LockCounter
from shardcount.reference import drive, expected_totals, make_plan
from shardcount.registry import Registry
from shardcount.sharded import ShardedCounter


class BasicTest(unittest.TestCase):
    def test_incr_returns_new_value_single_threaded(self):
        counter = ShardedCounter()
        self.assertEqual(counter.incr("a"), 1)
        self.assertEqual(counter.incr("a"), 2)
        self.assertEqual(counter.incr("a", 5), 7)

    def test_get_missing_key_is_zero(self):
        self.assertEqual(ShardedCounter().get("ghost"), 0)

    def test_negative_delta_allowed(self):
        counter = ShardedCounter()
        counter.incr("a", 3)
        self.assertEqual(counter.incr("a", -1), 2)
        self.assertEqual(counter.get("a"), 2)

    def test_zero_delta_leaves_key_hidden(self):
        counter = ShardedCounter()
        self.assertEqual(counter.incr("a", 0), 0)
        self.assertEqual(counter.keys(), [])

    def test_delta_must_be_int(self):
        with self.assertRaises(TypeError):
            ShardedCounter().incr("a", 1.5)

    def test_keys_lists_nonzero_keys_sorted(self):
        counter = ShardedCounter()
        counter.incr("b")
        counter.incr("a", 2)
        counter.incr("c")
        counter.incr("c", -1)
        self.assertEqual(counter.keys(), ["a", "b"])

    def test_total_sums_all_keys(self):
        counter = ShardedCounter()
        counter.incr("a", 2)
        counter.incr("b", -5)
        self.assertEqual(counter.total(), -3)

    def test_snapshot_returns_value_and_zeroes_key(self):
        counter = ShardedCounter()
        counter.incr("q", 4)
        self.assertEqual(counter.snapshot("q"), 4)
        self.assertEqual(counter.get("q"), 0)
        self.assertEqual(counter.keys(), [])

    def test_snapshot_missing_key_is_zero(self):
        self.assertEqual(ShardedCounter().snapshot("ghost"), 0)

    def test_snapshot_then_incr_starts_over(self):
        counter = ShardedCounter()
        counter.incr("q", 4)
        counter.snapshot("q")
        self.assertEqual(counter.incr("q", 2), 2)

    def test_stats_counts_operations(self):
        counter = ShardedCounter()
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
        counter = ShardedCounter(clock=lambda: 12.5)
        counter.incr("a")
        self.assertEqual(counter.stats().last_change, 12.5)

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            ShardedCounter(mode="ludicrous")

    def test_bad_batch_rejected(self):
        with self.assertRaises(ValueError):
            ShardedCounter(mode="fast", batch=0)


class ExactConcurrencyTest(unittest.TestCase):
    def test_parallel_incr_matches_lock_counter(self):
        plan = make_plan(seed=3, keys=("hot", "warm"), threads=8, per_thread=1000)
        sharded = ShardedCounter()
        drive(sharded, plan, barrier=threading.Barrier(len(plan)))
        lock = LockCounter()
        drive(lock, plan)
        want = {k: lock.get(k) for k in lock.keys()}
        self.assertEqual({k: sharded.get(k) for k in sharded.keys()}, want)
        self.assertEqual(want, expected_totals(plan))

    def test_hot_key_spreads_across_slots(self):
        plan = make_plan(seed=5, keys=("hot",), threads=8, per_thread=500)
        counter = ShardedCounter()
        drive(counter, plan)
        self.assertEqual(counter.slot_count, 8)
        spread = [v for v in counter.slot_values("hot") if v > 0]
        self.assertGreater(len(spread), 1)
        self.assertEqual(sum(counter.slot_values("hot")), counter.get("hot"))

    def test_snapshot_conserves_total_under_concurrency(self):
        plan = make_plan(seed=11, keys=("hot",), threads=8, per_thread=1500)
        expected = expected_totals(plan)["hot"]
        counter = ShardedCounter()
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


class FastModeTest(unittest.TestCase):
    def test_reads_lag_but_never_exceed_truth(self):
        counter = ShardedCounter(mode="fast", batch=100)
        for i in range(50):
            counter.incr("a")
            self.assertLessEqual(counter.get("a"), i + 1)
        self.assertLess(counter.get("a"), 50)  # 读确实滞后
        counter.sync()
        self.assertEqual(counter.get("a"), 50)

    def test_lag_bound_scales_with_batch(self):
        counter = ShardedCounter(mode="fast", batch=10)
        for _ in range(9):
            counter.incr("a")
        self.assertEqual(counter.get("a"), 0)  # 挂账未凑够一批
        counter.incr("a")  # 第 10 个触发落槽
        self.assertEqual(counter.get("a"), 10)

    def test_negative_delta_flushes_and_never_overshoots(self):
        counter = ShardedCounter(mode="fast", batch=100)
        for _ in range(30):
            counter.incr("a")
        counter.incr("a", -5)  # 负增量先把挂账落槽
        self.assertEqual(counter.get("a"), 25)

    def test_exact_after_worker_threads_finish(self):
        plan = make_plan(seed=17, keys=("hot", "warm"), threads=8, per_thread=1000)
        counter = ShardedCounter(mode="fast", batch=32)
        drive(counter, plan, barrier=threading.Barrier(len(plan)))
        # 写线程已收工，线程本地清理钩子把挂账落槽，不调 sync 也精确
        self.assertEqual(
            {k: counter.get(k) for k in counter.keys()}, expected_totals(plan)
        )

    def test_sync_makes_exact_mid_run(self):
        plan = make_plan(seed=19, keys=("hot",), threads=4, per_thread=500)
        counter = ShardedCounter(mode="fast", batch=1000)
        workers_done = threading.Event()

        def run(part):
            for key, delta in part:
                counter.incr(key, delta)

        workers = [threading.Thread(target=run, args=(part,)) for part in plan]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        workers_done.set()
        counter.sync()
        self.assertEqual(counter.get("hot"), expected_totals(plan)["hot"])

    def test_snapshot_flushes_and_conserves_total(self):
        plan = make_plan(seed=23, keys=("hot",), threads=8, per_thread=1500)
        expected = expected_totals(plan)["hot"]
        counter = ShardedCounter(mode="fast", batch=16)
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
        counter.sync()
        self.assertEqual(sum(taken) + counter.get("hot"), expected)
        self.assertGreater(len(taken), 0)


class RegistryModeTest(unittest.TestCase):
    def test_open_defaults_to_lock_counter(self):
        self.assertIsInstance(Registry().open("hits"), LockCounter)

    def test_open_with_mode_picks_sharded(self):
        registry = Registry()
        self.assertIsInstance(registry.open("a", mode="exact"), ShardedCounter)
        self.assertIsInstance(registry.open("b", mode="fast"), ShardedCounter)
        self.assertIsInstance(registry.open("c", mode="lock"), LockCounter)

    def test_open_same_name_ignores_later_mode(self):
        registry = Registry()
        first = registry.open("hits", mode="exact")
        self.assertIs(registry.open("hits"), first)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            Registry().open("hits", mode="ludicrous")

    def test_custom_factory_rejects_mode(self):
        registry = Registry(factory=lambda name: LockCounter())
        with self.assertRaises(ValueError):
            registry.open("hits", mode="fast")


if __name__ == "__main__":
    unittest.main()
