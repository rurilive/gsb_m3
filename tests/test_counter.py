"""基线测试：锁住 NaiveDigitCounter 改造前的现状行为。

这些断言针对的是闭区间上逐个整数枚举得到的确定结果，实现升级后必须原样满足，
本文件一字不许改动。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digitcount.counter import (  # noqa: E402
    DigitCountError,
    InvalidBoundError,
    InvalidDigitError,
    InvalidModError,
    NaiveDigitCounter,
)


class TestSumMod(unittest.TestCase):
    def setUp(self):
        self.nc = NaiveDigitCounter()

    def test_basic(self):
        self.assertEqual(self.nc.count_sum_mod(1, 100, 9, 0), 11)
        self.assertEqual(self.nc.count_sum_mod(1, 100, 9, 1), 12)

    def test_two_digit(self):
        self.assertEqual(self.nc.count_sum_mod(10, 99, 3, 0), 30)

    def test_degenerate_point(self):
        self.assertEqual(self.nc.count_sum_mod(0, 0, 5, 0), 1)

    def test_full_fixed(self):
        self.assertEqual(self.nc.count_sum_mod(100, 100, 10, 1), 1)

    def test_bad_rem(self):
        with self.assertRaises(InvalidModError):
            self.nc.count_sum_mod(1, 100, 9, 9)

    def test_bad_mod(self):
        with self.assertRaises(InvalidModError):
            self.nc.count_sum_mod(1, 100, 0, 0)


class TestContains(unittest.TestCase):
    def setUp(self):
        self.nc = NaiveDigitCounter()

    def test_basic(self):
        self.assertEqual(self.nc.count_contains(1, 100, 1), 20)

    def test_zero_leading(self):
        self.assertEqual(self.nc.count_contains(1, 100, 0), 10)

    def test_single_digit(self):
        self.assertEqual(self.nc.count_contains(1, 9, 5), 1)

    def test_full_fixed(self):
        self.assertEqual(self.nc.count_contains(1000, 1000, 0), 1)

    def test_bad_digit(self):
        with self.assertRaises(InvalidDigitError):
            self.nc.count_contains(1, 100, 10)
        with self.assertRaises(InvalidDigitError):
            self.nc.count_contains(1, 100, -1)


class TestMonotonic(unittest.TestCase):
    def setUp(self):
        self.nc = NaiveDigitCounter()

    def test_basic(self):
        self.assertEqual(self.nc.count_monotonic(1, 100), 54)

    def test_all_single(self):
        self.assertEqual(self.nc.count_monotonic(1, 9), 9)

    def test_two_digit(self):
        self.assertEqual(self.nc.count_monotonic(10, 99), 45)

    def test_range_thousand(self):
        self.assertEqual(self.nc.count_monotonic(1, 1000), 219)


class TestPalindrome(unittest.TestCase):
    def setUp(self):
        self.nc = NaiveDigitCounter()

    def test_basic(self):
        self.assertEqual(self.nc.count_palindrome(1, 100), 18)

    def test_single_digit(self):
        self.assertEqual(self.nc.count_palindrome(1, 9), 9)

    def test_two_digit(self):
        self.assertEqual(self.nc.count_palindrome(10, 100), 9)

    def test_range_thousand(self):
        self.assertEqual(self.nc.count_palindrome(1, 1000), 108)

    def test_zero(self):
        self.assertEqual(self.nc.count_palindrome(0, 0), 1)


class TestBoundsAndExceptions(unittest.TestCase):
    def setUp(self):
        self.nc = NaiveDigitCounter()

    def test_empty_range(self):
        self.assertEqual(self.nc.count_contains(5, 3, 1), 0)
        self.assertEqual(self.nc.count_palindrome(9, 1), 0)

    def test_zero_upper(self):
        self.assertEqual(self.nc.count_contains(0, 0, 0), 1)
        self.assertEqual(self.nc.count_monotonic(0, 0), 1)

    def test_bound_type(self):
        with self.assertRaises(InvalidBoundError):
            self.nc.count_contains("1", 100, 1)
        with self.assertRaises(InvalidBoundError):
            self.nc.count_palindrome(-1, 10)

    def test_hierarchy(self):
        self.assertTrue(issubclass(InvalidBoundError, DigitCountError))
        self.assertTrue(issubclass(InvalidDigitError, DigitCountError))
        self.assertTrue(issubclass(InvalidModError, DigitCountError))

    def test_deterministic(self):
        self.assertEqual(
            self.nc.count_contains(1, 100, 1), self.nc.count_contains(1, 100, 1)
        )
        self.assertEqual(
            self.nc.count_monotonic(1, 100), self.nc.count_monotonic(1, 100)
        )


if __name__ == "__main__":
    unittest.main()
