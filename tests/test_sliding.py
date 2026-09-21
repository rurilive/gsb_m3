"""滑动窗口行为测试：边界、事件时间推进、淘汰产出、迟到策略、多窗口、合并。"""

import unittest

from winagg.sliding import ClosedWindow, MultiWindowCounter, WindowedCounter


class FakeClock:
    """可手动改读数的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


class TestWindowBounds(unittest.TestCase):
    def test_window_interval_is_closed_open(self):
        c = WindowedCounter(10)
        c.add(0.0, 1)
        c.add(9.9, 2)
        self.assertEqual(c.window_total(), 3)
        self.assertEqual(c.current_window(), (0.0, 10.0))
        # 右边界开：ts=10 落在下一个窗口，并关闭 [0, 10)
        c.add(10.0, 5)
        self.assertEqual(c.current_window(), (10.0, 20.0))
        self.assertEqual(c.window_total(), 5)
        self.assertEqual(c.outputs(), [ClosedWindow(0.0, 10.0, 3)])

    def test_left_boundary_included(self):
        c = WindowedCounter(10)
        c.add(10.0, 1)
        c.add(20.0, 1)   # 关闭 [10, 20)
        c.add(30.0, 1)   # 关闭 [20, 30)
        self.assertEqual(c.outputs(),
                         [ClosedWindow(10.0, 20.0, 1),
                          ClosedWindow(20.0, 30.0, 1)])

    def test_event_exactly_on_boundary_lands_in_right_window(self):
        c = WindowedCounter(0.1)
        c.add(0.3, 5)    # 浮点边界：归 [0.3, 0.4)，不是 [0.2, 0.3)
        c.add(0.35, 1)
        self.assertEqual(c.window_total(), 6)
        c.add(0.45, 1)   # 关闭 [0.3, 0.4)
        self.assertEqual(len(c.outputs()), 1)
        self.assertAlmostEqual(c.outputs()[0].start, 0.3)
        self.assertEqual(c.outputs()[0].total, 6)

    def test_empty_counter_defaults(self):
        c = WindowedCounter(10)
        self.assertEqual(c.window_total(), 0)
        self.assertIsNone(c.current_window())
        self.assertIsNone(c.watermark())
        self.assertEqual(c.outputs(), [])
        self.assertEqual(c.late_count(), 0)


class TestEventTimeProgression(unittest.TestCase):
    def test_window_advances_by_event_time_not_arrival(self):
        clock = FakeClock(5000.0)
        c = WindowedCounter(10, clock=clock)
        c.add(0.0, 1)
        clock.now = 9000.0
        # 到达时刻跳了 4000，但事件时间只走到 5，窗口不关闭
        c.add(5.0, 2)
        self.assertEqual(c.current_window(), (0.0, 10.0))
        self.assertEqual(c.window_total(), 3)
        self.assertEqual(c.outputs(), [])
        # 事件时间越过 10 才关闭 [0, 10)
        c.add(10.0, 1)
        self.assertEqual(c.outputs(), [ClosedWindow(0.0, 10.0, 3)])

    def test_replay_is_reproducible_regardless_of_clock(self):
        def run(clock):
            c = WindowedCounter(10, clock=clock)
            for ts, v in [(3.0, 1), (12.0, 2), (7.0, 4), (25.0, 1)]:
                clock.now += 137.0
                c.add(ts, v)
            return c.outputs(), c.window_total()

        self.assertEqual(run(FakeClock(0.0)), run(FakeClock(99999.0)))

    def test_watermark_is_max_event_time(self):
        c = WindowedCounter(10)
        c.add(15.0, 1)
        c.add(9.0, 1)    # 乱序，水位线不回退
        self.assertEqual(c.watermark(), 15.0)


class TestEvictionOutput(unittest.TestCase):
    def test_closed_window_emits_output_record(self):
        c = WindowedCounter(10)
        c.add(1.0, 2)
        c.add(8.0, 3)
        c.add(11.0, 1)   # 关闭 [0, 10)
        self.assertEqual(c.outputs(), [ClosedWindow(0.0, 10.0, 5)])

    def test_on_close_callback_fires(self):
        seen = []
        c = WindowedCounter(10, on_close=seen.append)
        c.add(1.0, 2)
        c.add(11.0, 1)
        self.assertEqual(seen, [ClosedWindow(0.0, 10.0, 2)])

    def test_evicted_data_is_gone_from_open_window(self):
        c = WindowedCounter(10)
        c.add(1.0, 100)
        c.add(11.0, 1)
        # 老窗口淘汰后，当前窗口只剩新数据，不是查时装作看不见
        self.assertEqual(c.window_total(), 1)

    def test_gap_windows_produce_no_empty_output(self):
        c = WindowedCounter(10)
        c.add(1.0, 2)
        c.add(35.0, 1)   # 跳过多个空窗口，只产出有数据的
        self.assertEqual(c.outputs(), [ClosedWindow(0.0, 10.0, 2)])
        self.assertEqual(c.current_window(), (30.0, 40.0))


class TestLateEvents(unittest.TestCase):
    def test_late_event_inside_open_window_is_counted(self):
        c = WindowedCounter(10)
        c.add(10.0, 1)
        c.add(15.0, 1)
        self.assertEqual(c.add(12.0, 3), 5)   # 迟到但落在开口窗口内
        self.assertEqual(c.window_total(), 5)
        self.assertEqual(c.late_count(), 0)

    def test_late_event_before_left_boundary_dropped_by_default(self):
        c = WindowedCounter(10)
        c.add(15.0, 1)   # 水位线 15，[0,10) 已关闭
        self.assertIsNone(c.add(5.0, 7))
        self.assertEqual(c.window_total(), 1)
        self.assertEqual(c.late_count(), 1)
        self.assertEqual(c.late_total(), 0)

    def test_late_policy_count_accumulates_late_total(self):
        c = WindowedCounter(10, late_policy="count")
        c.add(15.0, 1)
        self.assertIsNone(c.add(5.0, 7))
        c.add(25.0, 1)   # 关闭 [10,20)，水位线 25
        c.add(8.0, 2)    # 仍迟到
        self.assertEqual(c.late_count(), 2)
        self.assertEqual(c.late_total(), 9)
        self.assertEqual(c.outputs(), [ClosedWindow(10.0, 20.0, 1)])

    def test_invalid_late_policy_rejected(self):
        with self.assertRaises(ValueError):
            WindowedCounter(10, late_policy="ignore")


class TestMultiWindow(unittest.TestCase):
    def test_windows_evict_independently(self):
        m = MultiWindowCounter([10, 30])
        for ts in [0.0, 5.0, 12.0, 25.0]:
            m.add(ts, 1)
        # 水位线 25：10 秒窗口已关闭 [0,10)、[10,20)，开口 [20,30)
        w10 = m.window(10)
        self.assertEqual(w10.outputs(), [ClosedWindow(0.0, 10.0, 2),
                                         ClosedWindow(10.0, 20.0, 1)])
        self.assertEqual(w10.window_total(), 1)
        # 30 秒窗口 [0,30) 仍开口，四条都在
        w30 = m.window(30)
        self.assertEqual(w30.outputs(), [])
        self.assertEqual(w30.window_total(), 4)
        self.assertEqual(m.totals(), {10: 1, 30: 4})

    def test_short_window_closes_first(self):
        m = MultiWindowCounter([10, 30])
        m.add(1.0, 1)
        m.add(11.0, 1)
        self.assertEqual(len(m.window(10).outputs()), 1)   # 短的到点就走
        self.assertEqual(len(m.window(30).outputs()), 0)

    def test_empty_sizes_rejected(self):
        with self.assertRaises(ValueError):
            MultiWindowCounter([])


class TestMerge(unittest.TestCase):
    def _counter_with_two_closed(self):
        c = WindowedCounter(10)
        c.add(1.0, 2)
        c.add(12.0, 3)
        c.add(25.0, 1)   # 关闭 [0,10) 与 [10,20)
        return c

    def test_merge_adjacent_closed_windows(self):
        c = self._counter_with_two_closed()
        merged = c.merge(0.0, 10.0)
        self.assertEqual(merged, ClosedWindow(0.0, 20.0, 5))
        self.assertEqual(c.outputs(), [ClosedWindow(0.0, 20.0, 5)])

    def test_merge_rejects_non_contiguous(self):
        c = WindowedCounter(10)
        c.add(1.0, 2)
        c.add(35.0, 1)   # 关闭 [0,10)，开口 [30,40)
        c.add(45.0, 1)   # 关闭 [30,40)
        with self.assertRaises(ValueError):
            c.merge(0.0, 30.0)

    def test_merge_rejects_expired_window(self):
        c = WindowedCounter(10, keep_outputs=1)
        c.add(1.0, 2)
        c.add(12.0, 3)
        c.add(25.0, 1)   # 缓冲只留 1 条，[0,10) 已过期
        self.assertEqual(c.outputs(), [ClosedWindow(10.0, 20.0, 3)])
        with self.assertRaises(ValueError):
            c.merge(0.0, 10.0)

    def test_merge_rejects_never_closed_window(self):
        c = WindowedCounter(10)
        c.add(1.0, 2)
        with self.assertRaises(ValueError):
            c.merge(0.0, 10.0)


if __name__ == "__main__":
    unittest.main()
