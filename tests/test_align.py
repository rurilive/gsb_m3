"""align 模块的行为基线。"""

import unittest

from stampkit import align


class FloorBucketTests(unittest.TestCase):
    def test_minute_bucket(self):
        self.assertEqual(align.floor_bucket(1_700_000_030_000, 60_000), 1_699_999_980_000)

    def test_value_on_bucket_stays(self):
        self.assertEqual(align.floor_bucket(1_700_000_040_000, 60_000), 1_700_000_040_000)

    def test_zero(self):
        self.assertEqual(align.floor_bucket(0, 60_000), 0)


class CeilBucketTests(unittest.TestCase):
    def test_not_aligned_rounds_up(self):
        self.assertEqual(align.ceil_bucket(1_700_000_030_000, 60_000), 1_700_000_040_000)

    def test_below_first_bucket(self):
        self.assertEqual(align.ceil_bucket(500, 60_000), 60_000)


class BucketIndexTests(unittest.TestCase):
    def test_hour_bucket_index(self):
        self.assertEqual(align.bucket_index(1_700_000_030_000, 3_600_000), 472_222)

    def test_minute_bucket_index(self):
        self.assertEqual(align.bucket_index(1_700_000_030_000, 60_000), 28_333_333)

    def test_second_interval_ignores_milliseconds(self):
        self.assertEqual(align.bucket_index(1_700_000_003_456, 1_000), 1_700_000_003)


class BucketSpanTests(unittest.TestCase):
    def test_exact_multiple_from_zero(self):
        self.assertEqual(align.bucket_span(0, 3_000, 1_000), 3)

    def test_partial_last_bucket(self):
        self.assertEqual(align.bucket_span(0, 2_500, 1_000), 3)

    def test_offset_start(self):
        self.assertEqual(align.bucket_span(100, 1_600, 1_000), 2)

    def test_empty_range(self):
        self.assertEqual(align.bucket_span(5_000, 5_000, 1_000), 0)


class AlignManyTests(unittest.TestCase):
    def test_batch_with_explicit_millis(self):
        values = [1_700_000_000_000, 1_700_000_002_500, 1_700_000_060_000]
        expected = [1_699_999_980_000, 1_699_999_980_000, 1_700_000_040_000]
        self.assertEqual(align.align_many(values, 60_000, unit="ms"), expected)

    def test_batch_with_seconds_source(self):
        values = [1_700_000_000, 1_700_000_002]
        expected = [1_699_999_980_000, 1_699_999_980_000]
        self.assertEqual(align.align_many(values, 60_000, unit="s"), expected)

    def test_batch_guess_on_millisecond_input(self):
        values = [1_700_000_000_000]
        self.assertEqual(align.align_many(values, 60_000), [1_699_999_980_000])


if __name__ == "__main__":
    unittest.main()
