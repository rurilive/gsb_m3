"""PalindromeTools 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from palx.strings import InvalidInputError, PalindromeTools, PalxError


class TestIsPalindrome(unittest.TestCase):
    def test_odd_palindrome(self):
        self.assertTrue(PalindromeTools("babad").is_palindrome(0, 3))

    def test_even_palindrome(self):
        self.assertTrue(PalindromeTools("cbbd").is_palindrome(1, 3))

    def test_not_palindrome(self):
        self.assertFalse(PalindromeTools("babad").is_palindrome(0, 4))

    def test_single_char_substring(self):
        self.assertTrue(PalindromeTools("babad").is_palindrome(2, 3))

    def test_empty_substring(self):
        self.assertTrue(PalindromeTools("babad").is_palindrome(2, 2))

    def test_full_string(self):
        self.assertTrue(PalindromeTools("racecar").is_palindrome(0, 7))


class TestCountPalindromes(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(PalindromeTools("banana").count_palindromes(), 10)

    def test_all_same(self):
        self.assertEqual(PalindromeTools("aaa").count_palindromes(), 6)

    def test_two_distinct(self):
        self.assertEqual(PalindromeTools("ab").count_palindromes(), 2)

    def test_single_char(self):
        self.assertEqual(PalindromeTools("x").count_palindromes(), 1)

    def test_empty_text(self):
        self.assertEqual(PalindromeTools("").count_palindromes(), 0)


class TestLongestPalindrome(unittest.TestCase):
    def test_odd_center(self):
        self.assertEqual(PalindromeTools("babad").longest_palindrome(), "bab")

    def test_even_center(self):
        self.assertEqual(PalindromeTools("cbbd").longest_palindrome(), "bb")

    def test_all_same(self):
        self.assertEqual(PalindromeTools("aaaa").longest_palindrome(), "aaaa")

    def test_single_char(self):
        self.assertEqual(PalindromeTools("x").longest_palindrome(), "x")

    def test_empty_text(self):
        self.assertEqual(PalindromeTools("").longest_palindrome(), "")

    def test_full_string_palindrome(self):
        self.assertEqual(PalindromeTools("racecar").longest_palindrome(), "racecar")

    def test_no_palindrome_longer_than_one(self):
        self.assertEqual(PalindromeTools("abcd").longest_palindrome(), "a")


class TestMinPalindromeCut(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(PalindromeTools("").min_palindrome_cut(), 0)

    def test_single_char(self):
        self.assertEqual(PalindromeTools("a").min_palindrome_cut(), 1)

    def test_two_distinct(self):
        self.assertEqual(PalindromeTools("ab").min_palindrome_cut(), 2)

    def test_whole_is_palindrome(self):
        self.assertEqual(PalindromeTools("abba").min_palindrome_cut(), 1)

    def test_needs_two_parts(self):
        self.assertEqual(PalindromeTools("aab").min_palindrome_cut(), 2)

    def test_all_distinct(self):
        self.assertEqual(PalindromeTools("abcd").min_palindrome_cut(), 4)


class TestCountPalindromeCut(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(PalindromeTools("").count_palindrome_cut(), 1)

    def test_single_char(self):
        self.assertEqual(PalindromeTools("a").count_palindrome_cut(), 1)

    def test_two_distinct(self):
        self.assertEqual(PalindromeTools("ab").count_palindrome_cut(), 1)

    def test_two_same(self):
        self.assertEqual(PalindromeTools("aa").count_palindrome_cut(), 2)

    def test_aaa(self):
        self.assertEqual(PalindromeTools("aaa").count_palindrome_cut(), 4)

    def test_aba(self):
        self.assertEqual(PalindromeTools("aba").count_palindrome_cut(), 2)


class TestExpandSteps(unittest.TestCase):
    def test_counts_matches(self):
        tools = PalindromeTools("aaaa")
        tools.longest_palindrome()
        self.assertGreater(tools.expand_steps(), 0)

    def test_repeat_same_count(self):
        tools = PalindromeTools("banana")
        tools.longest_palindrome()
        first = tools.expand_steps()
        tools.longest_palindrome()
        self.assertEqual(tools.expand_steps(), first)

    def test_empty_text_zero(self):
        tools = PalindromeTools("")
        tools.longest_palindrome()
        self.assertEqual(tools.expand_steps(), 0)


class TestErrors(unittest.TestCase):
    def test_non_string_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools(123)

    def test_negative_start_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools("abc").is_palindrome(-1, 1)

    def test_end_beyond_length_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools("abc").is_palindrome(0, 4)

    def test_reversed_range_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools("abc").is_palindrome(2, 1)

    def test_non_integer_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools("abc").is_palindrome(0, 1.5)

    def test_bool_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            PalindromeTools("abc").is_palindrome(True, 2)

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidInputError, PalxError))
        self.assertTrue(issubclass(PalxError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_result(self):
        tools = PalindromeTools("banana")
        self.assertEqual(tools.longest_palindrome(), tools.longest_palindrome())

    def test_count_stable(self):
        tools = PalindromeTools("banana")
        self.assertEqual(tools.count_palindromes(), tools.count_palindromes())

    def test_text_unchanged(self):
        tools = PalindromeTools("banana")
        tools.longest_palindrome()
        tools.count_palindromes()
        tools.min_palindrome_cut()
        self.assertEqual(tools.text(), "banana")


if __name__ == "__main__":
    unittest.main()
