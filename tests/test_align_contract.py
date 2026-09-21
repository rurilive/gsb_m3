"""事故复盘锁死用例：桶对齐、取整方向、覆盖计数与亚秒间隔。"""

import unittest

from stampkit import align
from stampkit.units import to_millis


class ExactBoundaryTests(unittest.TestCase):
    def test_point_exactly_on_bucket_stays(self):
        # 恰好落在整桶上的时间点不许被划进隔壁桶。
        self.assertEqual(align.floor_bucket(1_700_000_040_000, 60_000), 1_700_000_040_000)
        self.assertEqual(align.ceil_bucket(1_700_000_040_000, 60_000), 1_700_000_040_000)

    def test_subsecond_interval_boundary(self):
        self.assertEqual(align.floor_bucket(1_000, 250), 1_000)
        self.assertEqual(align.floor_bucket(999, 250), 750)
        self.assertEqual(align.ceil_bucket(750, 250), 750)
        self.assertEqual(align.ceil_bucket(751, 250), 1_000)

    def test_large_millis_no_float_drift(self):
        # 千年跨度的毫秒整数经过桶对齐必须精确，不能因浮点除法漂到隔壁桶。
        ts = 1_000 * 365 * 86_400 * 1000
        self.assertEqual(align.floor_bucket(ts, 60_000), ts)
        self.assertEqual(align.ceil_bucket(ts, 60_000), ts)
        self.assertEqual(align.floor_bucket(ts + 1, 60_000), ts)
        self.assertEqual(align.ceil_bucket(ts - 1, 60_000), ts)


class NegativeTimestampTests(unittest.TestCase):
    def test_floor_toward_minus_infinity(self):
        self.assertEqual(align.floor_bucket(-1, 60_000), -60_000)
        self.assertEqual(align.floor_bucket(-60_000, 60_000), -60_000)
        self.assertEqual(align.floor_bucket(-60_001, 60_000), -120_000)

    def test_ceil_toward_plus_infinity(self):
        self.assertEqual(align.ceil_bucket(-1, 60_000), 0)
        self.assertEqual(align.ceil_bucket(-60_000, 60_000), -60_000)
        self.assertEqual(align.ceil_bucket(-60_001, 60_000), -60_000)

    def test_negative_bucket_index(self):
        self.assertEqual(align.bucket_index(-1, 1000), -1)
        self.assertEqual(align.bucket_index(-1000, 1000), -1)
        self.assertEqual(align.bucket_index(-1001, 1000), -2)


class BucketSpanContractTests(unittest.TestCase):
    def test_unaligned_start_counts_covered_buckets(self):
        # [100, 1600) 触及桶 0 和桶 1，覆盖 2 个桶。
        self.assertEqual(align.bucket_span(100, 1_600, 1_000), 2)

    def test_endpoint_on_bucket_is_excluded(self):
        # 半开区间：end 恰好在桶上时，最后那个桶不算覆盖。
        self.assertEqual(align.bucket_span(0, 2_000, 1_000), 2)
        self.assertEqual(align.bucket_span(100, 2_000, 1_000), 2)
        self.assertEqual(align.bucket_span(100, 2_001, 1_000), 3)

    def test_negative_range(self):
        # [-2500, -500) 覆盖桶 -3、-2、-1，共 3 个。
        self.assertEqual(align.bucket_span(-2_500, -500, 1_000), 3)
        self.assertEqual(align.bucket_span(-2_500, -2_499, 1_000), 1)
        self.assertEqual(align.bucket_span(-1_000, 0, 1_000), 1)

    def test_reversed_and_empty(self):
        self.assertEqual(align.bucket_span(5_000, 5_000, 1_000), 0)
        self.assertEqual(align.bucket_span(6_000, 5_000, 1_000), 0)


class AlignManyContractTests(unittest.TestCase):
    def test_explicit_seconds_not_guessed_as_millis(self):
        values = [1_700_000_000, 1_700_000_060]
        expected = [1_699_999_980_000, 1_700_000_040_000]
        self.assertEqual(align.align_many(values, 60_000, unit="s"), expected)

    def test_explicit_millis_on_small_values(self):
        values = [1500, 2500]
        self.assertEqual(align.align_many(values, 1_000, unit="ms"), [1000, 2000])

    def test_equivalent_to_elementwise_calls(self):
        values = [1_700_000_000_123, 1_700_000_060_000, -1, -60_001]
        for unit in (None, "ms"):
            self.assertEqual(
                align.align_many(values, 60_000, unit=unit),
                [align.floor_bucket(to_millis(v, unit), 60_000) for v in values],
            )

    def test_seconds_floats_align_by_decimal_literal(self):
        values = [1_700_000_000.5, -0.0005]
        self.assertEqual(
            align.align_many(values, 1_000, unit="s"),
            [1_700_000_000_000, -1_000],
        )


if __name__ == "__main__":
    unittest.main()
