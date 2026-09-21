"""事故复盘后的契约锁定测试。

基线测试三条文件保持原样不动；这里把复盘结论单独锁死：
十进制精确换算、向负无穷取整、负时间戳、亚秒桶、整桶边界、
十三位毫秒判定与显式单位不被启发式翻盘、千年跨度归档。
"""

import unittest
from decimal import Decimal

from stampkit import align, span, units


class UnitGuessThresholdTests(unittest.TestCase):
    def test_boundary_is_ten_to_the_eleventh(self):
        self.assertEqual(units.guess_unit(99_999_999_999), "s")
        self.assertEqual(units.guess_unit(100_000_000_000), "ms")

    def test_ten_digit_seconds_and_thirteen_digit_millis(self):
        self.assertEqual(units.guess_unit(1_700_000_000), "s")
        self.assertEqual(units.guess_unit(1_700_000_000_123), "ms")

    def test_negative_magnitude_uses_absolute_value(self):
        self.assertEqual(units.guess_unit(-1_700_000_000), "s")
        self.assertEqual(units.guess_unit(-1_700_000_000_123), "ms")


class ExplicitUnitTests(unittest.TestCase):
    def test_explicit_seconds_scales_thirteen_digit_value(self):
        # 十三位量级显式按秒解释：必须 *1000，启发式不得翻盘。
        self.assertEqual(
            units.to_millis(1_700_000_000_000, unit="s"),
            1_700_000_000_000_000,
        )
        self.assertEqual(
            units.to_seconds(1_700_000_000_000, unit="s"),
            Decimal("1700000000000"),
        )

    def test_explicit_millis_on_small_value(self):
        self.assertEqual(units.to_millis(1500, unit="ms"), 1500)
        self.assertEqual(units.to_seconds(1500, unit="ms"), Decimal("1.5"))

    def test_explicit_millis_fractional_floors_toward_neg_infinity(self):
        self.assertEqual(units.to_millis(0.999, unit="ms"), 0)
        self.assertEqual(units.to_millis(-0.001, unit="ms"), -1)
        self.assertEqual(units.to_millis(-1.5, unit="ms"), -2)


class DecimalExactConversionTests(unittest.TestCase):
    def test_half_second_literal_scales_exactly(self):
        self.assertEqual(units.to_millis(1_234_567_890.5, unit="s"), 1_234_567_890_500)
        self.assertEqual(units.to_seconds(1_234_567_890.5, unit="s"), Decimal("1234567890.5"))

    def test_negative_half_second_floors_toward_neg_infinity(self):
        self.assertEqual(units.to_millis(-0.5, unit="s"), -500)
        self.assertEqual(units.to_millis(-1.5, unit="s"), -1_500)
        self.assertEqual(units.to_millis(-0.001, unit="s"), -1)

    def test_int_seconds_stay_on_integer_path(self):
        century_s = 3_155_760_000
        self.assertEqual(units.to_millis(century_s, unit="s"), 3_155_760_000_000)
        self.assertEqual(units.to_seconds(century_s, unit="s"), Decimal("3155760000"))

    def test_int_millis_pass_through_unscaled(self):
        self.assertEqual(units.to_millis(1_700_000_000_123), 1_700_000_000_123)
        self.assertEqual(units.to_millis(-1_700_000_000_123), -1_700_000_000_123)

    def test_to_seconds_always_decimal(self):
        self.assertIsInstance(units.to_seconds(90, unit="s"), Decimal)
        self.assertEqual(units.to_seconds(-1500, unit="ms"), Decimal("-1.5"))
        self.assertEqual(units.to_seconds(-0.5, unit="s"), Decimal("-0.5"))


class BucketBoundaryTests(unittest.TestCase):
    def test_value_exactly_on_bucket_is_not_pushed_next_bucket(self):
        self.assertEqual(align.floor_bucket(60_000, 60_000), 60_000)
        self.assertEqual(align.ceil_bucket(60_000, 60_000), 60_000)
        self.assertEqual(align.ceil_bucket(0, 60_000), 0)

    def test_sub_second_interval(self):
        self.assertEqual(align.floor_bucket(15, 10), 10)
        self.assertEqual(align.ceil_bucket(11, 10), 20)
        self.assertEqual(align.bucket_index(1_234, 100), 12)

    def test_negative_timestamps_floor_and_ceil(self):
        self.assertEqual(align.floor_bucket(-1, 60_000), -60_000)
        self.assertEqual(align.ceil_bucket(-1, 60_000), 0)
        self.assertEqual(align.floor_bucket(-60_000, 60_000), -60_000)
        self.assertEqual(align.bucket_index(-1, 60_000), -1)
        self.assertEqual(align.bucket_index(-60_000, 60_000), -1)

    def test_half_second_input_alignment(self):
        self.assertEqual(
            align.align_many([1_700_000_000.5], 60_000, unit="s"),
            [1_699_999_980_000],
        )
        self.assertEqual(align.align_many([-0.5], 1_000, unit="s"), [-1_000])


class BucketSpanContractTests(unittest.TestCase):
    def test_start_and_end_on_bucket_boundaries(self):
        self.assertEqual(align.bucket_span(1_000, 2_000, 1_000), 1)
        self.assertEqual(align.bucket_span(0, 3_000, 1_000), 3)

    def test_unaligned_start_counts_covered_buckets(self):
        self.assertEqual(align.bucket_span(999, 1_000, 1_000), 1)
        self.assertEqual(align.bucket_span(100, 1_100, 1_000), 2)

    def test_end_exclusive_does_not_count_next_bucket(self):
        self.assertEqual(align.bucket_span(0, 2_000, 1_000), 2)

    def test_negative_ranges(self):
        self.assertEqual(align.bucket_span(-500, 500, 1_000), 2)
        self.assertEqual(align.bucket_span(-2_000, -1_000, 1_000), 1)

    def test_reversed_and_empty_range(self):
        self.assertEqual(align.bucket_span(5_000, 5_000, 1_000), 0)
        self.assertEqual(align.bucket_span(5_000, 0, 1_000), 0)


class DurationFloorTests(unittest.TestCase):
    def test_negative_duration_floors_toward_neg_infinity(self):
        # -1500 ms 按秒：floor(-1.5) == -2，不是向零截断的 -1。
        self.assertEqual(span.duration_between(1_500, 0, "s"), -2)
        self.assertEqual(span.duration_between(0, -1_500, "s"), -2)

    def test_four_hundred_years_in_days_exact(self):
        four_hundred_years_ms = 400 * 365 * 86_400_000
        self.assertEqual(span.duration_between(0, four_hundred_years_ms, "d"), 400 * 365)

    def test_millennium_span_millis(self):
        millennium_ms = 1000 * 365 * 86_400_000
        self.assertEqual(span.duration_between(-millennium_ms, millennium_ms, "ms"), 2 * millennium_ms)


class ArchivePackTests(unittest.TestCase):
    def test_centuries_round_trip_without_overflow(self):
        # 旧实现乘 1_000_000 后超出 int64；契约单位就是毫秒。
        values = [
            100 * 365 * 86_400_000,
            1000 * 365 * 86_400_000,
            -1000 * 365 * 86_400_000,
            2**62,
            -(2**62),
        ]
        for value in values:
            blob = span.pack_duration(value)
            self.assertEqual(len(blob), 8)
            self.assertEqual(span.unpack_duration(blob), value)

    def test_pack_is_little_endian_signed_64bit_millis(self):
        self.assertEqual(span.pack_duration(90_000), (90_000).to_bytes(8, "little", signed=True))
        self.assertEqual(span.pack_duration(-1), b"\xff" * 8)


if __name__ == "__main__":
    unittest.main()
