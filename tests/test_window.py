"""滑动窗口 Histogram 的行为测试。"""

import threading
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的单调时钟。"""

    def __init__(self, start=0.0):
        self._now = start

    def __call__(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds
        return self._now


class TestWindowBasics(unittest.TestCase):
    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            Histogram(window_seconds=0)
        with self.assertRaises(ValueError):
            Histogram(window_seconds=-1)

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        self.assertEqual(h.observe(1), 0)
        clock.advance(5)
        self.assertEqual(h.observe(2), 0)
        # t=15 时 t=0 的样本年龄 15 > 10，被挤出；t=5 的保留
        clock.advance(10)
        self.assertEqual(h.observe(3), 1)
        self.assertEqual(h.count(), 2)

    def test_sample_exactly_at_window_boundary_stays(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(100)
        clock.advance(10)
        # 恰满 window_seconds 的样本仍算窗口内
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.observe(200), 0)
        self.assertEqual(h.count(), 2)
        clock.advance(1)
        self.assertEqual(h.observe(300), 1)

    def test_expired_window_raises_like_empty(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(100)
        clock.advance(11)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_count_and_percentiles_only_see_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)  # t=0
        clock.advance(6)
        h.observe(2)  # t=6
        clock.advance(5)
        h.observe(100)  # t=11，t=0 的样本被挤出
        self.assertEqual(h.count(), 2)
        self.assertEqual(h.percentiles(0.5), {0.5: 51.0})


class TestCompact(unittest.TestCase):
    def test_compact_returns_removed_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (1, 2, 3):
            h.observe(v)
        clock.advance(20)
        self.assertEqual(h.compact(), 3)
        self.assertEqual(h.count(), 0)
        self.assertEqual(h.compact(), 0)

    def test_compact_keeps_boundary_sample(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(10)
        self.assertEqual(h.compact(), 0)
        self.assertEqual(h.count(), 1)

    def test_compact_without_window_is_noop(self):
        h = Histogram()
        h.observe(1)
        self.assertEqual(h.compact(), 0)
        self.assertEqual(h.count(), 1)


class TestSnapshot(unittest.TestCase):
    def test_buckets_value_equal_edge_goes_right(self):
        h = Histogram()
        for v in (1, 10, 11, 50, 51):
            h.observe(v)
        # (-inf,10)、[10,50)、[50,+inf)：值等于边界归右桶
        self.assertEqual(h.snapshot([10, 50]), [1, 2, 2])

    def test_snapshot_reflects_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(5)
        clock.advance(11)
        h.observe(100)
        self.assertEqual(h.snapshot([10, 50]), [0, 0, 1])

    def test_snapshot_single_edge_and_empty(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        self.assertEqual(h.snapshot([0]), [0, 0])
        h.observe(-1)
        h.observe(1)
        self.assertEqual(h.snapshot([0]), [1, 1])

    def test_edges_must_be_strictly_increasing(self):
        h = Histogram()
        h.observe(1)
        with self.assertRaises(ValueError):
            h.snapshot([1, 1])
        with self.assertRaises(ValueError):
            h.snapshot([2, 1])


class TestConcurrentWindow(unittest.TestCase):
    """多线程 observe，用 Event 定节奏，注入时钟推进。"""

    N_THREADS = 4
    N_ROUNDS = 3

    def test_paced_concurrent_observes(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        stop = threading.Event()
        # 预分配每轮的放行/完成事件，worker 按下标访问，无列表增长竞态
        go = [
            [threading.Event() for _ in range(self.N_THREADS)]
            for _ in range(self.N_ROUNDS + 1)
        ]
        done = [
            [threading.Event() for _ in range(self.N_THREADS)]
            for _ in range(self.N_ROUNDS)
        ]
        evicted_per_thread = [[] for _ in range(self.N_THREADS)]
        threads = [
            threading.Thread(
                target=self._worker,
                args=(i, h, go, done, evicted_per_thread[i], stop),
            )
            for i in range(self.N_THREADS)
        ]
        for t in threads:
            t.start()

        # 第一轮 t=0：4 个样本，全在窗口内
        self._release(go[0], done[0])
        self.assertEqual(h.count(), 4)

        # 推进到 t=10（恰满窗口）：旧样本保留，挤出数为 0
        clock.advance(10)
        self._release(go[1], done[1])
        self.assertEqual(h.count(), 8)
        self.assertEqual(sum(sum(x) for x in evicted_per_thread), 0)

        # 推进到 t=11：t=0 的 4 个被挤出，挤出数由本轮 observe 承担
        clock.advance(1)
        self._release(go[2], done[2])
        self.assertEqual(h.count(), 8)
        self.assertEqual(sum(sum(x) for x in evicted_per_thread), 4)

        stop.set()
        for event in go[3]:
            event.set()
        for t in threads:
            t.join()

        # 窗口内只剩第二、三轮（值 2、3 各 4 个）
        ps = h.percentiles(0.5, 1.0)
        self.assertEqual(ps[0.5], 2.5)
        self.assertEqual(ps[1.0], 3)
        # 值 2 归边界 2 的右桶 [2,3)，值 3 归 [3,+inf)
        self.assertEqual(h.snapshot([1, 2, 3]), [0, 0, 4, 4])

    @staticmethod
    def _worker(worker_id, h, go, done, evicted, stop):
        round_index = 0
        while True:
            go[round_index][worker_id].wait()
            if stop.is_set():
                return
            evicted.append(h.observe(round_index + 1))
            done[round_index][worker_id].set()
            round_index += 1

    @staticmethod
    def _release(go_events, done_events):
        for event in go_events:
            event.set()
        for event in done_events:
            event.wait()


if __name__ == "__main__":
    unittest.main()
