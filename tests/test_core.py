"""TimestampLimiter 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from ratelimit.core import (
    DEFAULT_LABEL,
    RateLimitError,
    TimestampLimiter,
    naive_scan,
)


class TestTimestampLimiterBaseline(unittest.TestCase):
    def make(self, window=10, limit=3):
        return TimestampLimiter(window, limit)

    def test_default_label_constant(self):
        self.assertEqual(DEFAULT_LABEL, "default")

    def test_new_limiter_is_idle(self):
        lim = self.make()
        self.assertEqual(lim.window, 10)
        self.assertEqual(lim.limit, 3)
        self.assertEqual(lim.now, 0)
        self.assertEqual(lim.labels(), [])
        self.assertEqual(lim.history(), [])
        self.assertEqual(lim.total_rejected(), 0)
        self.assertEqual(lim.observed(0), 0)

    def test_error_is_exception(self):
        self.assertTrue(issubclass(RateLimitError, Exception))

    def test_allow_within_limit(self):
        lim = self.make(window=10, limit=3)
        self.assertTrue(lim.allow(1))
        self.assertTrue(lim.allow(2))
        self.assertTrue(lim.allow(3))
        self.assertFalse(lim.allow(4))

    def test_window_is_left_closed_right_open(self):
        lim = self.make(window=10, limit=1)
        self.assertTrue(lim.allow(0))
        # 时刻 10 距离 0 恰好等于窗口，按左闭右开口径不再算窗口内。
        self.assertTrue(lim.allow(10))

    def test_clock_only_moves_forward(self):
        lim = self.make(window=10, limit=1)
        lim.allow(5)
        self.assertEqual(lim.now, 5)
        self.assertFalse(lim.allow(4))
        self.assertEqual(lim.now, 5)

    def test_scattered_window_count(self):
        lim = self.make(window=10, limit=10)
        self.assertTrue(lim.allow(0))
        self.assertTrue(lim.allow(5))
        # 时刻 11 时，0 已滑出窗口，只剩 5 与 11 两笔。
        self.assertTrue(lim.allow(11))
        self.assertEqual(lim.observed(11), 2)

    def test_cost_consumes_quota(self):
        lim = self.make(window=10, limit=3)
        self.assertTrue(lim.allow(1, cost=2))
        # 窗口内已放行成本为 2，本笔成本 1 合计 3，仍在额度内。
        self.assertTrue(lim.allow(2, cost=1))
        # 窗口内已放行成本为 3，本笔成本 1 合计 4 超过额度，拒绝。
        self.assertFalse(lim.allow(3, cost=1))
        self.assertEqual(lim.total_rejected(), 1)

    def test_observed_does_not_record(self):
        lim = self.make(window=10, limit=3)
        lim.allow(1)
        lim.allow(2)
        before = lim.history()
        self.assertEqual(lim.observed(3), 2)
        self.assertEqual(lim.history(), before)

    def test_history_records_each_judgement(self):
        lim = self.make(window=10, limit=1)
        lim.allow(0)
        lim.allow(1)
        self.assertEqual(lim.history(), [(0, 1, 0, True), (1, 1, 1, False)])
        out = lim.history()
        out.append("junk")
        self.assertEqual(len(lim.history()), 2)

    def test_total_rejected_counts_denials(self):
        lim = self.make(window=10, limit=1)
        lim.allow(0)
        lim.allow(1)
        lim.allow(2)
        self.assertEqual(lim.total_rejected(), 2)

    def test_labels_isolated(self):
        lim = self.make(window=10, limit=1)
        self.assertTrue(lim.allow(1, label="a"))
        self.assertTrue(lim.allow(1, label="b"))
        self.assertFalse(lim.allow(1, label="a"))
        self.assertEqual(lim.total_rejected("a"), 1)
        self.assertEqual(lim.total_rejected("b"), 0)
        self.assertEqual(lim.labels(), ["a", "b"])

    def test_labels_sorted_and_deduped(self):
        lim = self.make(window=10, limit=5)
        lim.allow(1, label="c")
        lim.allow(1, label="a")
        lim.allow(1, label="a")
        lim.allow(1, label="b")
        self.assertEqual(lim.labels(), ["a", "b", "c"])

    def test_default_label_participates_in_labels(self):
        lim = self.make(window=10, limit=5)
        lim.allow(1)
        lim.allow(1, label="z")
        self.assertEqual(lim.labels(), ["default", "z"])

    def test_unknown_label_reads_idle(self):
        lim = self.make()
        self.assertEqual(lim.observed(100, label="ghost"), 0)
        self.assertEqual(lim.total_rejected("ghost"), 0)
        self.assertEqual(lim.history("ghost"), [])

    def test_rejects_bad_window(self):
        with self.assertRaises(RateLimitError):
            TimestampLimiter(0, 3)
        with self.assertRaises(RateLimitError):
            TimestampLimiter(-1, 3)

    def test_rejects_bad_limit(self):
        with self.assertRaises(RateLimitError):
            TimestampLimiter(10, 0)
        with self.assertRaises(RateLimitError):
            TimestampLimiter(10, -2)

    def test_rejects_bad_cost(self):
        lim = self.make()
        with self.assertRaises(RateLimitError):
            lim.allow(1, cost=0)

    def test_naive_scan_matches_window_rule(self):
        # 时刻 10 时窗口为 (0, 10]，落在其中的是 5、9、10 三笔。
        self.assertEqual(naive_scan([0, 5, 9, 10, 20], 10, 10), 3)
        self.assertEqual(naive_scan([], 10, 5), 0)
        self.assertEqual(naive_scan([100], 10, 5), 0)

    def test_many_requests_accumulate_exactly(self):
        lim = self.make(window=1000, limit=10 ** 9)
        for i in range(500):
            self.assertTrue(lim.allow(i))
        self.assertEqual(lim.observed(499), 500)
        self.assertEqual(lim.total_rejected(), 0)

    def test_repeated_runs_are_deterministic(self):
        def run():
            lim = TimestampLimiter(10, 2)
            out = []
            for t in (0, 3, 6, 9, 12, 15, 18):
                out.append(lim.allow(t))
            return out, lim.total_rejected(), lim.observed(18)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
