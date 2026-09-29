"""基线测试：锁住 NaiveStats 的现状行为。

这是改造前的基线，一字不许改，必须始终全绿。
"""

import unittest

from statlib.running import NaiveStats, StatError


class TestPushAndCount(unittest.TestCase):
    def test_count_starts_at_zero(self):
        self.assertEqual(NaiveStats().count(), 0)

    def test_push_grows_count(self):
        s = NaiveStats()
        for x in (3, 1, 2):
            s.push(x)
        self.assertEqual(s.count(), 3)

    def test_ints_and_floats_both_accepted(self):
        s = NaiveStats()
        s.push(1)
        s.push(2.5)
        self.assertEqual(s.count(), 2)

    def test_non_number_rejected(self):
        s = NaiveStats()
        for bad in ("1", None, [1], True):
            with self.assertRaises(StatError):
                s.push(bad)
        self.assertEqual(s.count(), 0)


class TestMean(unittest.TestCase):
    def test_empty_mean_is_none(self):
        self.assertIsNone(NaiveStats().mean())

    def test_mean_of_values(self):
        s = NaiveStats()
        for x in (1.0, 2.0, 3.0, 4.0):
            s.push(x)
        self.assertEqual(s.mean(), 2.5)


class TestMedian(unittest.TestCase):
    def test_empty_median_is_none(self):
        self.assertIsNone(NaiveStats().median())

    def test_single_value(self):
        s = NaiveStats()
        s.push(7)
        self.assertEqual(s.median(), 7.0)

    def test_odd_count_takes_middle(self):
        s = NaiveStats()
        for x in (5, 1, 3):
            s.push(x)
        self.assertEqual(s.median(), 3.0)

    def test_even_count_averages_two_middles(self):
        s = NaiveStats()
        for x in (4, 1, 3, 2):
            s.push(x)
        self.assertEqual(s.median(), 2.5)

    def test_order_of_insert_does_not_matter(self):
        a = NaiveStats()
        b = NaiveStats()
        for x in (9, 2, 7, 4, 1):
            a.push(x)
        for x in (1, 2, 4, 7, 9):
            b.push(x)
        self.assertEqual(a.median(), b.median())


class TestMinMax(unittest.TestCase):
    def test_empty_min_max_are_none(self):
        s = NaiveStats()
        self.assertIsNone(s.min())
        self.assertIsNone(s.max())

    def test_min_max_values(self):
        s = NaiveStats()
        for x in (4, -2, 8, 0):
            s.push(x)
        self.assertEqual(s.min(), -2.0)
        self.assertEqual(s.max(), 8.0)


class TestSortedValues(unittest.TestCase):
    def test_sorted_values_are_sorted(self):
        s = NaiveStats()
        for x in (3, 1, 2):
            s.push(x)
        self.assertEqual(s.sorted_values(), [1.0, 2.0, 3.0])

    def test_sorted_values_is_a_copy(self):
        s = NaiveStats()
        for x in (2, 1):
            s.push(x)
        snapshot = s.sorted_values()
        snapshot.append(99.0)
        self.assertEqual(s.count(), 2)
        self.assertEqual(s.sorted_values(), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
