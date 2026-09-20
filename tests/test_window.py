"""滑动窗口 Histogram 的行为测试：窗口判定、挤出返回值、compact、分桶。"""

import threading
import time
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的时钟，供窗口测试注入。"""

    def __init__(self, start=0.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestWindowSemantics(unittest.TestCase):
    def test_sample_exactly_at_window_edge_stays_inside(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(100)
        clock.advance(10)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.99), {0.99: 100})

    def test_sample_just_past_window_edge_is_outside(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(100)
        clock.advance(10 + 1e-9)
        self.assertEqual(h.count(), 0)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_count_and_percentiles_only_see_live_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        clock.advance(3)
        h.observe(2)
        clock.advance(3)
        h.observe(3)
        # t=0 的样本（1）在 t=6 已出窗，t=3、t=6 的样本仍在
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.percentiles(0.0, 1.0), {0.0: 2, 1.0: 3})

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        self.assertEqual(h.observe(1), 0)
        self.assertEqual(h.observe(2), 0)
        clock.advance(6)
        self.assertEqual(h.observe(3), 2)
        self.assertEqual(h.observe(4), 0)
        self.assertEqual(h.count(), 2)

    def test_default_behavior_unchanged_without_window(self):
        h = Histogram()
        self.assertEqual(h.observe(1), 0)
        h.observe(2)
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.compact(), 0)


class TestLazyCleanupAndCompact(unittest.TestCase):
    def test_count_does_not_physically_remove(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(6)
        self.assertEqual(h.count(), 0)
        # 惰性：过期样本仍物理保留，直到 observe 或 compact 清理
        self.assertEqual(len(h._values), 2)

    def test_compact_removes_and_reports_stale(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        clock.advance(2)
        h.observe(2)
        clock.advance(4)
        removed = h.compact()
        self.assertEqual(removed, 1)
        self.assertEqual(len(h._values), 1)
        self.assertEqual(h._values, [2])
        self.assertEqual(h.compact(), 0)

    def test_observe_physically_evicts_stale(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(6)
        h.observe(3)
        self.assertEqual(h._values, [3])

    def test_compact_mixed_with_lazy_expiry(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for t, v in ((0, 1), (2, 2), (4, 3), (12, 9)):
            clock.now = t
            h.observe(v)
        # t=12 时 observe 挤掉 t=0（t=2 恰满窗口仍保留）
        clock.now = 20
        self.assertEqual(h.compact(), 2)  # t=2、t=4 已过期，t=12 恰满 8 秒保留
        self.assertEqual(h._values, [9])


class TestSnapshot(unittest.TestCase):
    def test_buckets_with_equal_edges_go_right(self):
        clock = FakeClock()
        h = Histogram(window_seconds=100, clock=clock)
        for v in (0, 10, 10, 25, 100, 101):
            h.observe(v)
        # 桶: (<=10), (10,25], (25,100], (>100]；值等于边界归右桶
        self.assertEqual(h.snapshot([10, 25, 100]), [1, 2, 1, 2])

    def test_snapshot_empty_edges(self):
        clock = FakeClock()
        h = Histogram(window_seconds=100, clock=clock)
        h.observe(1)
        h.observe(2)
        self.assertEqual(h.snapshot([]), [2])

    def test_snapshot_only_counts_window_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        clock.advance(6)
        h.observe(50)
        self.assertEqual(h.snapshot([10, 100]), [0, 1, 0])

    def test_snapshot_rejects_non_strict_edges(self):
        h = Histogram(window_seconds=5)
        with self.assertRaises(ValueError):
            h.snapshot([1, 1])
        with self.assertRaises(ValueError):
            h.snapshot([2, 1])


class TestConstruction(unittest.TestCase):
    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            Histogram(window_seconds=0)
        with self.assertRaises(ValueError):
            Histogram(window_seconds=-1)

    def test_default_clock_is_monotonic(self):
        h = Histogram(window_seconds=0.05)
        h.observe(1)
        time.sleep(0.06)
        self.assertEqual(h.count(), 0)


class TestWindowConcurrency(unittest.TestCase):
    def test_waved_concurrent_observes_follow_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)

        def run_wave(wave_start, values):
            release = threading.Event()
            ready_events = [threading.Event() for _ in range(4)]

            def worker(ready):
                ready.set()
                release.wait()
                for v in values:
                    h.observe(v)

            threads = [
                threading.Thread(target=worker, args=(ready,))
                for ready in ready_events
            ]
            for t in threads:
                t.start()
            for ready in ready_events:
                ready.wait()
            # 所有线程就位后，主线程统一推进注入时钟再放行
            clock.now = wave_start
            release.set()
            for t in threads:
                t.join()

        run_wave(0, range(1, 26))      # 4 线程各记 1..25，共 100
        self.assertEqual(h.count(), 100)
        clock.now = 5
        run_wave(5, range(100, 125))   # 与上一波同在窗口内
        self.assertEqual(h.count(), 200)
        clock.now = 10                 # t=0 恰满窗口，仍算窗口内
        self.assertEqual(h.count(), 200)
        clock.now = 10 + 1e-9
        self.assertEqual(h.count(), 100)  # 第一波全部挤出


if __name__ == "__main__":
    unittest.main()
