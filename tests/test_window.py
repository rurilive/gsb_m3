"""滑动窗口行为的测试：注入时钟推进 + 多线程 observe。"""

import threading
import time
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的时钟，注入 Histogram 替代 time.monotonic。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestNoWindowUnchanged(unittest.TestCase):
    def test_no_window_keeps_everything(self):
        clock = FakeClock()
        h = Histogram(clock=clock)
        for v in (1, 2, 3):
            self.assertEqual(h.observe(v), 0)
        clock.advance(1000)
        self.assertEqual(h.count(), 3)
        self.assertEqual(h.compact(), 0)
        self.assertEqual(h.percentiles(0.5), {0.5: 2})
        self.assertEqual(h.snapshot([2]), [1, 2])


class TestWindowSemantics(unittest.TestCase):
    def test_samples_within_window_are_counted(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        h.observe(10)
        clock.advance(59)
        h.observe(20)
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.percentiles(0.5), {0.5: 15.0})

    def test_exact_window_age_stays_in_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        h.observe(10)
        clock.advance(60)  # 恰满 window_seconds，算窗口内
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 10})

    def test_expired_samples_leave_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        h.observe(10)
        clock.advance(61)
        self.assertEqual(h.count(), 0)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        for v in (1, 2, 3):
            self.assertEqual(h.observe(v), 0)
        clock.advance(61)
        self.assertEqual(h.observe(4), 3)
        self.assertEqual(h.observe(5), 0)
        self.assertEqual(h.count(), 2)

    def test_reads_do_not_purge(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        h.observe(10)
        clock.advance(61)
        self.assertEqual(h.count(), 0)   # 读路径只过滤不删除
        h.snapshot([5])
        self.assertEqual(h.compact(), 1)  # 样本仍在，compact 才清理
        self.assertEqual(h.compact(), 0)

    def test_compact_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        for v in (1, 2, 3):
            h.observe(v)
        clock.advance(30)
        self.assertEqual(h.observe(4), 0)
        clock.advance(31)  # 前三个样本 61s 前，出窗口；第四个 31s 前，在窗口内
        self.assertEqual(h.compact(), 3)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 4})


class TestSnapshot(unittest.TestCase):
    def test_bucket_counts_with_right_ownership(self):
        h = Histogram(window_seconds=60, clock=FakeClock())
        for v in (5, 10, 10, 15, 20, 25):
            h.observe(v)
        # 边界 10、20：值等于边界归右桶
        self.assertEqual(h.snapshot([10, 20]), [1, 3, 2])

    def test_edges_must_be_strictly_increasing(self):
        h = Histogram(window_seconds=60, clock=FakeClock())
        h.observe(1)
        with self.assertRaises(ValueError):
            h.snapshot([10, 10])
        with self.assertRaises(ValueError):
            h.snapshot([20, 10])

    def test_snapshot_only_counts_window_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        h.observe(1)
        clock.advance(61)
        h.observe(2)
        self.assertEqual(h.snapshot([10]), [1, 0])


class TestConcurrentWindow(unittest.TestCase):
    def test_concurrent_observe_across_window_advance(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        start_first = threading.Event()
        start_second = threading.Event()
        threads = [
            threading.Thread(
                target=self._observe_two_batches,
                args=(h, start_first, start_second),
            )
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        start_first.set()
        deadline = time.monotonic() + 5
        while h.count() < 1000:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.001)
        clock.advance(5)
        start_second.set()
        for t in threads:
            t.join()
        self.assertEqual(h.count(), 2000)
        # 第一批 10.1s 前已出窗口，第二批 5.1s 前仍在窗口内
        clock.advance(5.1)
        self.assertEqual(h.count(), 1000)
        self.assertEqual(h.percentiles(0.5)[0.5], 375.5)
        self.assertEqual(h.observe(1), 1000)
        self.assertEqual(h.count(), 1001)

    @staticmethod
    def _observe_two_batches(h, start_first, start_second):
        start_first.wait()
        for v in range(1, 251):
            h.observe(v)
        start_second.wait()
        for v in range(251, 501):
            h.observe(v)


if __name__ == "__main__":
    unittest.main()
