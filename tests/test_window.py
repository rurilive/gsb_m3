"""滑动窗口行为的测试：注入时钟推进，覆盖窗口内外、返回值、分桶、compact。"""

import threading
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的时钟，直接可调用。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestWindowBasics(unittest.TestCase):
    def test_no_window_behavior_unchanged(self):
        h = Histogram()
        self.assertEqual(h.observe(1), 0)
        h.observe(2)
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.percentiles(0.5), {0.5: 1.5})
        self.assertEqual(h.compact(), 0)

    def test_samples_expire_after_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(11)
        self.assertEqual(h.count(), 0)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_sample_exactly_window_old_stays(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(10)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 1})
        clock.advance(0.001)
        self.assertEqual(h.count(), 0)

    def test_percentiles_only_count_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (100, 200, 300):
            h.observe(v)
        clock.advance(11)
        h.observe(5)
        h.observe(15)
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.percentiles(0.5), {0.5: 10.0})

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        self.assertEqual(h.observe(1), 0)
        self.assertEqual(h.observe(2), 0)
        clock.advance(10)
        # 恰满窗口的样本仍在窗口内，不触发清理
        self.assertEqual(h.observe(3), 0)
        clock.advance(1)
        # 两个 ts=0 的样本过期，被本次 observe 挤出
        self.assertEqual(h.observe(4), 2)
        self.assertEqual(h.observe(5), 0)

    def test_compact_removes_expired_and_reports(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(11)
        self.assertEqual(h.compact(), 2)
        self.assertEqual(h.compact(), 0)
        h.observe(3)
        self.assertEqual(h.count(), 1)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_buckets_value_on_edge_goes_right(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        for v in (5, 10, 15, 20, 25, 30, 35):
            h.observe(v)
        # 边界 10/20/30：(-inf,10) [10,20) [20,30) [30,inf)
        self.assertEqual(h.snapshot([10, 20, 30]), [1, 2, 2, 2])

    def test_snapshot_only_counts_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (1, 2, 3):
            h.observe(v)
        clock.advance(11)
        h.observe(100)
        self.assertEqual(h.snapshot([50]), [0, 1])

    def test_snapshot_rejects_non_increasing_edges(self):
        h = Histogram(window_seconds=10, clock=FakeClock())
        with self.assertRaises(ValueError):
            h.snapshot([10, 10])
        with self.assertRaises(ValueError):
            h.snapshot([20, 10])

    def test_snapshot_without_window(self):
        h = Histogram()
        for v in (1, 2, 3):
            h.observe(v)
        self.assertEqual(h.snapshot([2]), [1, 2])


class TestWindowThreadSafety(unittest.TestCase):
    def test_concurrent_observe_with_injected_clock(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(999)  # 旧样本，窗口推进后应被某个线程挤出
        clock.advance(11)
        start = threading.Event()
        evicted = []
        evicted_lock = threading.Lock()
        threads = [
            threading.Thread(
                target=self._observe_batch, args=(h, start, evicted, evicted_lock)
            )
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()
        self.assertEqual(h.count(), 1000)
        # 旧样本恰好被一个 observe 挤出，返回值总和为 1
        self.assertEqual(sum(evicted), 1)
        self.assertEqual(h.percentiles(0.5)[0.5], 125.5)

    @staticmethod
    def _observe_batch(h, start, evicted, evicted_lock):
        start.wait()
        for v in range(1, 251):
            n = h.observe(v)
            if n:
                with evicted_lock:
                    evicted.append(n)


if __name__ == "__main__":
    unittest.main()
