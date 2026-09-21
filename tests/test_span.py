"""span 模块的行为基线。"""

import unittest

from stampkit import span


class DurationBetweenTests(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(span.duration_between(1_700_000_000_000, 1_700_000_090_000, "s"), 90)

    def test_minutes(self):
        self.assertEqual(span.duration_between(0, 7_200_000, "min"), 120)

    def test_default_unit_is_millis(self):
        self.assertEqual(span.duration_between(1_700_000_000_000, 1_700_000_003_000), 3_000)

    def test_days(self):
        self.assertEqual(span.duration_between(0, 86_400_000, "d"), 1)

    def test_partial_unit_is_truncated_for_positive_spans(self):
        self.assertEqual(span.duration_between(0, 1_999, "s"), 1)


class FormatDurationTests(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(span.format_duration(1_500), "1.500s")

    def test_minutes(self):
        self.assertEqual(span.format_duration(90_000), "1m 30.000s")

    def test_full_chain(self):
        self.assertEqual(span.format_duration(90_061_500), "1d 1h 1m 1.500s")

    def test_zero(self):
        self.assertEqual(span.format_duration(0), "0.000s")

    def test_negative(self):
        self.assertEqual(span.format_duration(-1_500), "-1.500s")


class PackDurationTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(span.unpack_duration(span.pack_duration(90_000)), 90_000)

    def test_negative_round_trip(self):
        self.assertEqual(span.unpack_duration(span.pack_duration(-1_500)), -1_500)

    def test_thirty_days_round_trip(self):
        thirty_days = 30 * 86_400_000
        self.assertEqual(span.unpack_duration(span.pack_duration(thirty_days)), thirty_days)

    def test_fixed_width(self):
        self.assertEqual(len(span.pack_duration(1)), 8)


if __name__ == "__main__":
    unittest.main()
