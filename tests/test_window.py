"""滑动窗口行为的测试：注入时钟推进 + Event 定节奏的多线程 observe。"""

import threading
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的注入时钟。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class TestWindowExpiry(unittest.TestCase):
    def test_count_only_in_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(11)
        h.observe(3)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 3})

    def test_exact_window_age_stays_in_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(10)
        self.assertEqual(h.count(), 1)
        clock.advance(0.001)
        self.assertEqual(h.count(), 0)

    def test_percentiles_reflect_recent_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        for v in (100, 200, 300):
            h.observe(v)
        clock.advance(6)
        for v in (1, 2, 3, 4):
            h.observe(v)
        self.assertEqual(h.percentiles(0.5), {0.5: 2.5})

    def test_empty_after_expiry_raises(self):
        clock = FakeClock()
        h = Histogram(window_seconds=1, clock=clock)
        h.observe(1)
        clock.advance(2)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)


class TestObserveReturnAndCompact(unittest.TestCase):
    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        self.assertEqual(h.observe(1), 0)
        self.assertEqual(h.observe(2), 0)
        clock.advance(11)
        self.assertEqual(h.observe(3), 2)
        self.assertEqual(h.observe(4), 0)

    def test_no_window_observe_returns_zero(self):
        h = Histogram()
        self.assertEqual(h.observe(1), 0)

    def test_compact_removes_expired_and_returns_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(11)
        # 惰性：count 已按窗口过滤，但旧样本尚未物理清理
        self.assertEqual(h.count(), 0)
        self.assertEqual(h.compact(), 2)
        self.assertEqual(h.compact(), 0)

    def test_compact_without_window_is_noop(self):
        h = Histogram()
        h.observe(1)
        self.assertEqual(h.compact(), 0)
        self.assertEqual(h.count(), 1)


class TestSnapshot(unittest.TestCase):
    def test_buckets_only_count_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (5, 15, 25):
            h.observe(v)
        clock.advance(11)
        for v in (1, 12, 22, 99):
            h.observe(v)
        self.assertEqual(h.snapshot([10, 20]), [1, 1, 2])

    def test_value_equal_to_edge_goes_right(self):
        h = Histogram()
        for v in (10, 20, 20, 5):
            h.observe(v)
        self.assertEqual(h.snapshot([10, 20]), [1, 1, 2])

    def test_edges_must_be_strictly_increasing(self):
        h = Histogram()
        with self.assertRaises(ValueError):
            h.snapshot([10, 10])
        with self.assertRaises(ValueError):
            h.snapshot([20, 10])

    def test_empty_edges_single_bucket(self):
        h = Histogram()
        h.observe(1)
        self.assertEqual(h.snapshot([]), [1])


class TestWindowThreadSafety(unittest.TestCase):
    def test_concurrent_observe_then_mass_expiry(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        start = threading.Event()
        threads = [
            threading.Thread(target=self._observe_batch, args=(h, start))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()
        self.assertEqual(h.count(), 1000)
        clock.advance(11)
        self.assertEqual(h.observe(1), 1000)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 1})

    @staticmethod
    def _observe_batch(h, start):
        start.wait()
        for v in range(1, 251):
            h.observe(v)


if __name__ == "__main__":
    unittest.main()
