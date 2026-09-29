"""基线测试：锁住 BruteDigits 改造前的现状行为。

这些断言针对的是一到上界逐个整数枚举得到的确定结果，实现升级后必须原样满足，
本文件一字不许改动。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digitx.count import (  # noqa: E402
    BruteDigits,
    DigitError,
    InvalidBoundError,
    InvalidDigitError,
)


class TestCountWithDigit(unittest.TestCase):
    def setUp(self):
        self.bd = BruteDigits()

    def test_plain(self):
        self.assertEqual(self.bd.count_with_digit(100, 1), 20)

    def test_zero_first_leading(self):
        self.assertEqual(self.bd.count_with_digit(10, 0), 1)

    def test_zero_larger(self):
        self.assertEqual(self.bd.count_with_digit(1000, 0), 181)

    def test_eight(self):
        self.assertEqual(self.bd.count_with_digit(88, 8), 17)

    def test_single(self):
        self.assertEqual(self.bd.count_with_digit(9, 9), 1)
        self.assertEqual(self.bd.count_with_digit(1, 1), 1)

    def test_bad_digit(self):
        with self.assertRaises(InvalidDigitError):
            self.bd.count_with_digit(10, 10)
        with self.assertRaises(InvalidDigitError):
            self.bd.count_with_digit(10, -1)


class TestSumOfDigits(unittest.TestCase):
    def setUp(self):
        self.bd = BruteDigits()

    def test_single(self):
        self.assertEqual(self.bd.sum_of_digits(1), 1)
        self.assertEqual(self.bd.sum_of_digits(9), 45)

    def test_basic(self):
        self.assertEqual(self.bd.sum_of_digits(10), 46)
        self.assertEqual(self.bd.sum_of_digits(100), 901)

    def test_nines(self):
        self.assertEqual(self.bd.sum_of_digits(999), 13500)


class TestCountLessThan(unittest.TestCase):
    def setUp(self):
        self.bd = BruteDigits()

    def test_basic(self):
        self.assertEqual(self.bd.count_less_than(50, 30), 30)
        self.assertEqual(self.bd.count_less_than(100, 100), 100)
        self.assertEqual(self.bd.count_less_than(100, 7), 7)

    def test_zero(self):
        self.assertEqual(self.bd.count_less_than(10, 0), 0)

    def test_above_n(self):
        self.assertEqual(self.bd.count_less_than(5, 99), 5)


class TestCountDivisible(unittest.TestCase):
    def setUp(self):
        self.bd = BruteDigits()

    def test_basic(self):
        self.assertEqual(self.bd.count_divisible(100, 7), 14)
        self.assertEqual(self.bd.count_divisible(1000, 7), 142)

    def test_one(self):
        self.assertEqual(self.bd.count_divisible(1000, 1), 1000)

    def test_ten(self):
        self.assertEqual(self.bd.count_divisible(97, 10), 9)

    def test_bad_divisor(self):
        with self.assertRaises(DigitError):
            self.bd.count_divisible(10, 0)


class TestExceptions(unittest.TestCase):
    def setUp(self):
        self.bd = BruteDigits()

    def test_bound_type(self):
        with self.assertRaises(InvalidBoundError):
            self.bd.count_with_digit("10", 1)
        with self.assertRaises(InvalidBoundError):
            self.bd.sum_of_digits(-1)

    def test_digit_type(self):
        with self.assertRaises(InvalidDigitError):
            self.bd.count_with_digit(10, "1")

    def test_hierarchy(self):
        self.assertTrue(issubclass(InvalidBoundError, DigitError))
        self.assertTrue(issubclass(InvalidDigitError, DigitError))


if __name__ == "__main__":
    unittest.main()
