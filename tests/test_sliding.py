"""SlidingWindow / MultiWindow 行为测试。

窗口只随事件时间推进，注入时钟仅用于给关闭产出盖时刻。
"""

import unittest

from winagg.sliding import ClosedWindow, LateEventError, MultiWindow, SlidingWindow


class FakeClock:
    """可手动推进的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def tick(self, dt):
        self.now += dt


class TestSlidingWindowBounds(unittest.TestCase):
    def test_sum_over_recent_window_by_event_time(self):
        w = SlidingWindow(10)
        w.add(100.0, 2)
        w.add(103.0, 5)
        w.add(101.0, 1)          # 乱序但落在窗口内
        self.assertEqual(w.sum(), 8)
        self.assertEqual(w.watermark(), 103.0)
        self.assertEqual(w.bounds(), (93.0, 103.0))

    def test_empty_window(self):
        w = SlidingWindow(10)
        self.assertEqual(w.sum(), 0)
        self.assertEqual(w.count(), 0)
        self.assertIsNone(w.watermark())
        self.assertIsNone(w.bounds())

    def test_left_boundary_is_closed(self):
        w = SlidingWindow(10)
        w.add(100.0, 1)
        w.add(90.0, 2)           # 恰好左边界，计入
        self.assertEqual(w.sum(), 3)
        w.add(89.999, 4)         # 早于左边界，判迟到
        self.assertEqual(w.sum(), 3)
        self.assertEqual(w.late_count(), 1)
        self.assertEqual(w.late_total(), 4)

    def test_bucket_boundary_is_closed_open(self):
        w = SlidingWindow(10)
        w.add(0.0, 1)
        w.add(10.0, 2)           # 边界点归 [10,20)，不归 [0,10)
        w.add(20.0, 4)           # 推进使 [0,10) 关闭
        closed = w.closed()
        self.assertEqual(len(closed), 1)
        self.assertEqual((closed[0].start, closed[0].end), (0.0, 10.0))
        self.assertEqual(closed[0].total, 1)
        self.assertEqual(closed[0].count, 1)

    def test_eviction_is_real_not_query_time_filter(self):
        w = SlidingWindow(10)
        for ts in range(0, 100, 5):
            w.add(float(ts), 1)
        # watermark=95，窗口 [85,95]，旧事件已被物理淘汰
        self.assertEqual(w.count(), 3)
        self.assertEqual(w.sum(), 3)
        self.assertEqual(len(w._events), 3)


class TestEventTimeAdvance(unittest.TestCase):
    def test_window_advances_by_event_time_not_arrival(self):
        clock = FakeClock(1000.0)
        w = SlidingWindow(10, clock=clock)
        clock.now = 5000.0
        w.add(100.0, 1)          # 到达时刻 5000，窗口仍按事件时间
        self.assertEqual(w.bounds(), (90.0, 100.0))
        clock.now = 9999.0
        w.add(105.0, 1)
        self.assertEqual(w.bounds(), (95.0, 105.0))

    def test_watermark_never_moves_backward(self):
        w = SlidingWindow(10)
        w.add(100.0, 1)
        w.add(95.0, 1)           # 更老的事件不拉回水位线
        self.assertEqual(w.watermark(), 100.0)
        self.assertEqual(w.bounds(), (90.0, 100.0))

    def test_replay_is_reproducible(self):
        events = [(1.0, 2), (3.0, 1), (2.0, 5), (25.0, 1), (26.0, 3)]

        def run(clock_start):
            clock = FakeClock(clock_start)
            w = SlidingWindow(10, clock=clock)
            for ts, v in events:
                clock.tick(7.0)
                w.add(ts, v)
            closed = [(c.start, c.end, c.total, c.count) for c in w.closed()]
            return w.sum(), w.count(), closed

        self.assertEqual(run(0.0), run(9999.0))


class TestLatePolicy(unittest.TestCase):
    def test_out_of_order_within_window_is_counted(self):
        w = SlidingWindow(10)
        w.add(100.0, 1)
        w.add(95.0, 2)           # 迟到但落在窗口内
        self.assertEqual(w.sum(), 3)
        self.assertEqual(w.late_count(), 0)

    def test_drop_policy_counts_and_returns_none(self):
        w = SlidingWindow(10, on_late="drop")
        w.add(100.0, 1)
        self.assertIsNone(w.add(50.0, 7))
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.late_count(), 1)
        self.assertEqual(w.late_total(), 7)

    def test_raise_policy(self):
        w = SlidingWindow(10, on_late="raise")
        w.add(100.0, 1)
        with self.assertRaises(LateEventError):
            w.add(50.0, 7)
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.late_count(), 1)
        self.assertEqual(w.late_total(), 7)

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            SlidingWindow(10, on_late="ignore")


class TestClosedOutput(unittest.TestCase):
    def test_closed_output_recorded_when_window_pushed_out(self):
        clock = FakeClock()
        w = SlidingWindow(10, clock=clock)
        w.add(1.0, 2)
        w.add(5.0, 3)
        clock.now = 777.0
        w.add(20.0, 1)           # watermark=20，[0,10) 被挤出
        closed = w.closed()
        self.assertEqual(len(closed), 1)
        c = closed[0]
        self.assertIsInstance(c, ClosedWindow)
        self.assertEqual((c.start, c.end, c.total, c.count), (0.0, 10.0, 5, 2))
        self.assertEqual(c.closed_at, 777.0)

    def test_drain_closed_empties_outputs(self):
        w = SlidingWindow(10)
        w.add(1.0, 2)
        w.add(20.0, 1)
        drained = w.drain_closed()
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0].total, 2)
        self.assertEqual(w.closed(), [])

    def test_late_event_after_close_does_not_change_output(self):
        w = SlidingWindow(10)
        w.add(1.0, 2)
        w.add(20.0, 1)           # [0,10) 关闭，total=2
        w.add(3.0, 100)          # 已迟到，丢弃
        self.assertEqual(w.closed()[0].total, 2)
        self.assertEqual(w.late_count(), 1)


class TestMergeClosed(unittest.TestCase):
    def _window_with_two_closed(self, **kw):
        w = SlidingWindow(10, **kw)
        w.add(1.0, 2)
        w.add(11.0, 3)
        w.add(30.0, 1)           # 关闭 [0,10) 与 [10,20)
        return w

    def test_merge_adjacent_closed_windows(self):
        w = self._window_with_two_closed()
        merged = w.merge_closed(0.0, 10.0)
        self.assertEqual((merged.start, merged.end), (0.0, 20.0))
        self.assertEqual((merged.total, merged.count), (5, 2))
        remaining = w.closed()
        self.assertEqual(len(remaining), 1)
        self.assertEqual((remaining[0].start, remaining[0].end), (0.0, 20.0))

    def test_merge_requires_contiguous(self):
        w = self._window_with_two_closed()
        w.add(21.0, 1)
        w.add(40.0, 1)           # 再关闭 [20,30)
        with self.assertRaises(ValueError):
            w.merge_closed(0.0, 20.0)

    def test_merge_requires_both_unexpired(self):
        w = SlidingWindow(10, closed_retention=25)
        w.add(1.0, 1)
        w.add(11.0, 1)
        w.add(30.0, 1)           # 关闭 [0,10)、[10,20)，均未过期
        w.add(40.0, 1)           # watermark=40，[0,10) 过期被清除
        self.assertEqual([c.start for c in w.closed()], [10.0])
        with self.assertRaises(KeyError):
            w.merge_closed(0.0, 10.0)

    def test_merge_missing_window_raises(self):
        w = self._window_with_two_closed()
        with self.assertRaises(KeyError):
            w.merge_closed(0.0, 50.0)


class TestMultiWindow(unittest.TestCase):
    def test_windows_evict_independently(self):
        mw = MultiWindow([10, 60])
        for ts in range(0, 100, 5):
            mw.add(float(ts), 1)
        # watermark=95：短窗口只剩 [85,95]，长窗口还留着 [35,95]
        self.assertEqual(mw.sum(10), 3)
        self.assertEqual(mw.count(10), 3)
        self.assertEqual(mw.sum(60), 13)
        self.assertEqual(mw.count(60), 13)

    def test_short_window_closes_earlier(self):
        mw = MultiWindow([10, 60])
        mw.add(1.0, 2)
        mw.add(20.0, 1)
        self.assertEqual(len(mw.window(10).closed()), 1)   # [0,10) 已关闭
        self.assertEqual(len(mw.window(60).closed()), 0)   # 长窗口还没推到

    def test_add_returns_per_window_sums(self):
        mw = MultiWindow([10, 60])
        self.assertEqual(mw.add(5.0, 2), {10.0: 2, 60.0: 2})
        self.assertEqual(mw.lengths(), [10.0, 60.0])

    def test_late_event_applies_per_window(self):
        mw = MultiWindow([10, 60])
        mw.add(100.0, 1)
        res = mw.add(85.0, 2)    # 对 10 秒窗口迟到，对 60 秒窗口正常
        self.assertIsNone(res[10.0])
        self.assertEqual(res[60.0], 3)
        self.assertEqual(mw.window(10).late_count(), 1)
        self.assertEqual(mw.window(60).late_count(), 0)


if __name__ == "__main__":
    unittest.main()
