"""滑动窗口行为的测试：注入时钟、Event 定节奏的多线程 observe。"""

import threading
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的时钟，线程安全。"""

    def __init__(self, start=0.0):
        self._lock = threading.Lock()
        self._now = start

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, dt):
        with self._lock:
            self._now += dt


class TestNoWindowUnchanged(unittest.TestCase):
    def test_observe_returns_none_without_window(self):
        h = Histogram()
        self.assertIsNone(h.observe(1))
        self.assertEqual(h.count(), 1)

    def test_compact_is_noop_without_window(self):
        h = Histogram()
        h.observe(1)
        self.assertEqual(h.compact(), 0)
        self.assertEqual(h.count(), 1)

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            Histogram(window_seconds=0)
        with self.assertRaises(ValueError):
            Histogram(window_seconds=-1)


class TestWindowBoundaries(unittest.TestCase):
    def test_old_samples_leave_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(6)
        self.assertEqual(h.count(), 0)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_exactly_window_seconds_old_stays(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(42)
        clock.advance(5)  # 恰满 window_seconds，仍算窗口内
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 42})
        clock.advance(0.001)
        self.assertEqual(h.count(), 0)

    def test_percentiles_reflect_recent_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (1000, 2000, 3000):  # 切流前的高延迟
            h.observe(v)
        clock.advance(11)
        for v in (10, 20, 30):  # 切流后的新常态
            h.observe(v)
        self.assertEqual(h.count(), 3)
        self.assertEqual(h.percentiles(0.5), {0.5: 20})


class TestObserveReturnValue(unittest.TestCase):
    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        self.assertEqual(h.observe(1), 0)
        self.assertEqual(h.observe(2), 0)
        self.assertEqual(h.observe(3), 0)
        clock.advance(6)
        self.assertEqual(h.observe(4), 3)  # 本次挤出 3 个旧样本
        self.assertEqual(h.observe(5), 0)  # 已挤过，不再重复计
        self.assertEqual(h.count(), 2)


class TestCompact(unittest.TestCase):
    def test_compact_evicts_and_reports(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        h.observe(2)
        self.assertEqual(h.compact(), 0)  # 未过期，没有可清理的
        self.assertEqual(h.count(), 2)
        clock.advance(6)
        self.assertEqual(h.compact(), 2)
        self.assertEqual(h.compact(), 0)  # 清理是幂等的
        self.assertEqual(h.count(), 0)


class TestSnapshot(unittest.TestCase):
    def test_bucket_counts_with_edge_on_right(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        for v in (5, 10, 15, 20, 25):
            h.observe(v)
        # 值等于边界归右桶：10 进 [10,20)，20 进 >=20
        self.assertEqual(h.snapshot([10, 20]), [1, 2, 2])

    def test_snapshot_only_counts_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(100)
        clock.advance(6)
        h.observe(1)
        self.assertEqual(h.snapshot([10, 20]), [1, 0, 0])

    def test_snapshot_empty_edges(self):
        h = Histogram(window_seconds=60, clock=FakeClock())
        h.observe(7)
        self.assertEqual(h.snapshot([]), [1])

    def test_snapshot_requires_strictly_increasing_edges(self):
        h = Histogram(window_seconds=60, clock=FakeClock())
        with self.assertRaises(ValueError):
            h.snapshot([10, 10])
        with self.assertRaises(ValueError):
            h.snapshot([20, 10])


class TestConcurrentWindowedObserve(unittest.TestCase):
    def test_threads_paced_by_events_with_injected_clock(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        n = 3
        begin = threading.Event()
        second_phase = threading.Event()
        first_done = [threading.Event() for _ in range(n)]
        second_done = [threading.Event() for _ in range(n)]
        evicted = [None] * n

        def worker(i):
            begin.wait()
            h.observe(i + 1)  # t=0：1, 2, 3
            first_done[i].set()
            second_phase.wait()
            evicted[i] = h.observe(100 + i)  # t=15：旧样本应被挤出
            second_done[i].set()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()

        begin.set()
        for e in first_done:
            e.wait()
        self.assertEqual(h.count(), 3)

        clock.advance(15)  # 第一批样本全部滑出窗口
        second_phase.set()
        for e in second_done:
            e.wait()
        for t in threads:
            t.join()

        # 三个线程合计恰好挤出 3 个旧样本（锁保证只挤一次）
        self.assertEqual(sum(evicted), 3)
        self.assertEqual(sorted(evicted).count(0), 2)
        self.assertEqual(h.count(), 3)
        self.assertEqual(h.percentiles(0.5), {0.5: 101})
        self.assertEqual(h.snapshot([100, 101, 102]), [0, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
