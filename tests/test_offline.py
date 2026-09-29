"""BruteQueries 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一个固定数组上逐项重扫的结果：不同值个数、众数出现次数、
出现次数平方和、朴素代价计数，以及非法区间必须 fail fast。
"""

import unittest

from molib.offline import BadRange, BruteQueries, MoError

# 固定数组：
#   下标  0  1  2  3  4  5  6  7
#   值    1  2  1  3  2  1  4  2
FIXED_DATA = [1, 2, 1, 3, 2, 1, 4, 2]


def build():
    return BruteQueries(FIXED_DATA)


class TestStructure(unittest.TestCase):
    def test_size(self):
        self.assertEqual(build().size(), 8)

    def test_data_returns_copy(self):
        q = build()
        got = q.data
        got.append(999)
        self.assertEqual(q.data, FIXED_DATA)


class TestDistinct(unittest.TestCase):
    def test_full_range(self):
        self.assertEqual(build().distinct(0, 8), 4)

    def test_small_ranges(self):
        q = build()
        self.assertEqual(q.distinct(0, 1), 1)
        self.assertEqual(q.distinct(0, 3), 2)
        self.assertEqual(q.distinct(3, 6), 3)
        self.assertEqual(q.distinct(6, 8), 2)

    def test_empty_range(self):
        self.assertEqual(build().distinct(4, 4), 0)


class TestModeCount(unittest.TestCase):
    def test_full_range(self):
        # 1 出现 3 次、2 出现 3 次，并列，返回 3
        self.assertEqual(build().mode_count(0, 8), 3)

    def test_small_ranges(self):
        q = build()
        self.assertEqual(q.mode_count(0, 3), 2)
        self.assertEqual(q.mode_count(2, 6), 2)
        self.assertEqual(q.mode_count(6, 8), 1)

    def test_empty_range(self):
        self.assertEqual(build().mode_count(5, 5), 0)


class TestSumOfSquares(unittest.TestCase):
    def test_full_range(self):
        # 1 三次、2 三次、3 一次、4 一次：9 + 9 + 1 + 1
        self.assertEqual(build().sum_of_squares(0, 8), 20)

    def test_small_ranges(self):
        q = build()
        self.assertEqual(q.sum_of_squares(0, 3), 5)
        self.assertEqual(q.sum_of_squares(1, 5), 6)
        self.assertEqual(q.sum_of_squares(6, 8), 2)

    def test_empty_range(self):
        self.assertEqual(build().sum_of_squares(3, 3), 0)


class TestBruteCost(unittest.TestCase):
    def test_cost_is_interval_length(self):
        q = build()
        self.assertEqual(q.brute_cost(0, 8), 8)
        self.assertEqual(q.brute_cost(3, 6), 3)
        self.assertEqual(q.brute_cost(4, 4), 0)


class TestBadRanges(unittest.TestCase):
    def test_negative_left(self):
        with self.assertRaises(BadRange):
            build().distinct(-1, 3)

    def test_right_beyond_size(self):
        with self.assertRaises(BadRange):
            build().mode_count(0, 9)

    def test_reversed_range(self):
        with self.assertRaises(BadRange):
            build().sum_of_squares(5, 2)

    def test_bad_range_is_mo_error(self):
        self.assertTrue(issubclass(BadRange, MoError))

    def test_reversed_range_is_mo_error(self):
        with self.assertRaises(MoError):
            build().distinct(7, 3)


if __name__ == "__main__":
    unittest.main()
