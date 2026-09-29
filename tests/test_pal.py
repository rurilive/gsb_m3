"""BrutePal 现状行为的锁定测试（改造前基线，一个字都不许改）。

用固定串把当前那套枚举子串的做法所给出的事实逐项钉死：判断某段是不是回文、
最长回文是谁、回文子串总数是多少、以及给定中心的最长回文半径是多少。这些
数字都是基线实现实际算出来的，任何一次改动只要动摇了既有对外行为，这里就
会红。
"""

import unittest

from palindromex.pal import BrutePal, PalError

S = "abaxyzzyxf"


class TestIsPalindrome(unittest.TestCase):
    def setUp(self):
        self.p = BrutePal(S)

    def test_single_char_is_palindrome(self):
        self.assertTrue(self.p.is_palindrome(0, 1))
        self.assertTrue(self.p.is_palindrome(9, 10))
        self.assertTrue(self.p.is_palindrome(2, 3))

    def test_empty_span_is_palindrome(self):
        self.assertTrue(self.p.is_palindrome(3, 3))
        self.assertTrue(self.p.is_palindrome(0, 0))

    def test_true_spans(self):
        self.assertTrue(self.p.is_palindrome(0, 3))   # aba
        self.assertTrue(self.p.is_palindrome(3, 9))   # xyzzyx
        self.assertTrue(self.p.is_palindrome(4, 8))   # yzzy
        self.assertTrue(self.p.is_palindrome(5, 7))   # zz

    def test_false_spans(self):
        self.assertFalse(self.p.is_palindrome(0, 2))  # ab
        self.assertFalse(self.p.is_palindrome(1, 3))  # ba
        self.assertFalse(self.p.is_palindrome(0, 10))


class TestLongestPalindrome(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(BrutePal(S).longest_palindrome(), "xyzzyx")

    def test_all_equal(self):
        self.assertEqual(BrutePal("aaa").longest_palindrome(), "aaa")

    def test_empty(self):
        self.assertEqual(BrutePal("").longest_palindrome(), "")


class TestCountPalindromes(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(BrutePal(S).count_palindromes(), 14)

    def test_all_equal(self):
        self.assertEqual(BrutePal("aaa").count_palindromes(), 6)

    def test_empty(self):
        self.assertEqual(BrutePal("").count_palindromes(), 0)


class TestEachCenterMax(unittest.TestCase):
    def test_radius_table_mixed(self):
        got = [BrutePal(S).each_center_max(k) for k in range(2 * len(S) + 1)]
        self.assertEqual(
            got,
            [1, 0, 2, 0, 1, 0, 1, 0, 1, 0, 1, 3, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        )

    def test_radius_table_all_equal(self):
        p = BrutePal("aaa")
        self.assertEqual([p.each_center_max(k) for k in range(7)], [1, 1, 2, 1, 1, 0, 1])

    def test_center_count(self):
        self.assertEqual(BrutePal(S).each_center_max(11), 3)   # 中心在整个串正中
        self.assertEqual(BrutePal(S).each_center_max(0), 1)    # 首个字符中心


class TestErrors(unittest.TestCase):
    def test_non_string_text(self):
        with self.assertRaises(PalError):
            BrutePal(123)

    def test_span_out_of_range(self):
        p = BrutePal("ab")
        for lo, hi in [(0, 3), (-1, 1), (1, 0)]:
            with self.assertRaises(PalError):
                p.is_palindrome(lo, hi)

    def test_center_out_of_range(self):
        p = BrutePal("ab")
        with self.assertRaises(PalError):
            p.each_center_max(-1)
        with self.assertRaises(PalError):
            p.each_center_max(2 * len(p) + 1)


if __name__ == "__main__":
    unittest.main()
