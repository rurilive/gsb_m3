"""基线测试：锁住 NaivePercentileStream 的现状行为。

这是改造前的基线，一字不许改，必须始终全绿。
"""

import unittest

from pctstream.stream import NaivePercentileStream, StreamError


class TestPushAndCount(unittest.TestCase):
    def test_count_starts_at_zero(self):
        self.assertEqual(NaivePercentileStream().count(), 0)

    def test_push_grows_count(self):
        s = NaivePercentileStream()
        for x in (3, 1, 2):
            s.push(x)
        self.assertEqual(s.count(), 3)

    def test_ints_and_floats_both_accepted(self):
        s = NaivePercentileStream()
        s.push(1)
        s.push(2.5)
        self.assertEqual(s.count(), 2)

    def test_non_number_rejected(self):
        s = NaivePercentileStream()
        for bad in ("1", None, [1], True):
            with self.assertRaises(StreamError):
                s.push(bad)
        self.assertEqual(s.count(), 0)


class TestMedian(unittest.TestCase):
    def test_empty_median_is_none(self):
        self.assertIsNone(NaivePercentileStream().median())

    def test_single_value(self):
        s = NaivePercentileStream()
        s.push(7)
        self.assertEqual(s.median(), 7.0)

    def test_odd_count_takes_middle(self):
        s = NaivePercentileStream()
        for x in (5, 1, 3):
            s.push(x)
        self.assertEqual(s.median(), 3.0)

    def test_even_count_averages_two_middles(self):
        s = NaivePercentileStream()
        for x in (4, 1, 3, 2):
            s.push(x)
        self.assertEqual(s.median(), 2.5)

    def test_order_of_insert_does_not_matter(self):
        a = NaivePercentileStream()
        b = NaivePercentileStream()
        for x in (9, 2, 7, 4, 1):
            a.push(x)
        for x in (1, 2, 4, 7, 9):
            b.push(x)
        self.assertEqual(a.median(), b.median())


class TestQuantile(unittest.TestCase):
    def test_empty_quantile_is_none(self):
        self.assertIsNone(NaivePercentileStream().quantile(50))

    def test_zero_and_hundred_are_ends(self):
        s = NaivePercentileStream()
        for x in (4, 1, 9, 2):
            s.push(x)
        self.assertEqual(s.quantile(0), 1.0)
        self.assertEqual(s.quantile(100), 9.0)

    def test_fifty_equals_lower_middle_for_even(self):
        s = NaivePercentileStream()
        for x in (1, 2, 3, 4):
            s.push(x)
        self.assertEqual(s.quantile(50), 2.0)

    def test_quantile_matches_sorted_position(self):
        s = NaivePercentileStream()
        for x in (5, 1, 4, 2, 3):
            s.push(x)
        self.assertEqual(s.quantile(20), 1.0)
        self.assertEqual(s.quantile(60), 3.0)

    def test_non_integer_quantile_rejected(self):
        s = NaivePercentileStream()
        s.push(1)
        for bad in (1.5, "50", None, True):
            with self.assertRaises(StreamError):
                s.quantile(bad)

    def test_out_of_range_quantile_rejected(self):
        s = NaivePercentileStream()
        s.push(1)
        for bad in (-1, 101):
            with self.assertRaises(StreamError):
                s.quantile(bad)


class TestMinMaxSorted(unittest.TestCase):
    def test_empty_min_max_are_none(self):
        s = NaivePercentileStream()
        self.assertIsNone(s.min())
        self.assertIsNone(s.max())

    def test_min_max_values(self):
        s = NaivePercentileStream()
        for x in (4, -2, 8, 0):
            s.push(x)
        self.assertEqual(s.min(), -2.0)
        self.assertEqual(s.max(), 8.0)

    def test_sorted_values_are_sorted(self):
        s = NaivePercentileStream()
        for x in (3, 1, 2):
            s.push(x)
        self.assertEqual(s.sorted_values(), [1.0, 2.0, 3.0])

    def test_sorted_values_is_a_copy(self):
        s = NaivePercentileStream()
        for x in (2, 1):
            s.push(x)
        snapshot = s.sorted_values()
        snapshot.append(99.0)
        self.assertEqual(s.count(), 2)
        self.assertEqual(s.sorted_values(), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
