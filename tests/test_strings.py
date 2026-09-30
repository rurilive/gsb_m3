"""StringTools 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from hashx.strings import HashxError, InvalidInputError, StringTools


class TestEqual(unittest.TestCase):
    def test_equal_same_span(self):
        tools = StringTools("banana")
        self.assertTrue(tools.equal(1, 4, 1, 4))

    def test_equal_two_occurrences(self):
        tools = StringTools("banana")
        self.assertTrue(tools.equal(1, 4, 3, 6))

    def test_not_equal_different_content(self):
        tools = StringTools("banana")
        self.assertFalse(tools.equal(0, 3, 1, 4))

    def test_not_equal_different_length(self):
        tools = StringTools("banana")
        self.assertFalse(tools.equal(0, 2, 0, 3))

    def test_empty_ranges_are_equal(self):
        tools = StringTools("banana")
        self.assertTrue(tools.equal(2, 2, 4, 4))

    def test_empty_range_versus_nonempty(self):
        tools = StringTools("banana")
        self.assertFalse(tools.equal(2, 2, 2, 3))

    def test_full_string(self):
        tools = StringTools("abc")
        self.assertTrue(tools.equal(0, 3, 0, 3))


class TestLongestRepeat(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(StringTools("banana").longest_repeat(), "ana")

    def test_no_repeat(self):
        self.assertEqual(StringTools("abc").longest_repeat(), "")

    def test_all_same(self):
        self.assertEqual(StringTools("aaaa").longest_repeat(), "aaa")

    def test_simple_pair(self):
        self.assertEqual(StringTools("abab").longest_repeat(), "ab")

    def test_empty_text(self):
        self.assertEqual(StringTools("").longest_repeat(), "")

    def test_single_char(self):
        self.assertEqual(StringTools("x").longest_repeat(), "")


class TestLongestPalindrome(unittest.TestCase):
    def test_odd_center(self):
        self.assertEqual(StringTools("babad").longest_palindrome(), "bab")

    def test_even_center(self):
        self.assertEqual(StringTools("cbbd").longest_palindrome(), "bb")

    def test_all_same(self):
        self.assertEqual(StringTools("aaaa").longest_palindrome(), "aaaa")

    def test_single_char(self):
        self.assertEqual(StringTools("x").longest_palindrome(), "x")

    def test_empty_text(self):
        self.assertEqual(StringTools("").longest_palindrome(), "")

    def test_full_string_palindrome(self):
        self.assertEqual(StringTools("racecar").longest_palindrome(), "racecar")


class TestLongestCommonSubstring(unittest.TestCase):
    def test_basic(self):
        tools = StringTools("abcdef")
        self.assertEqual(tools.longest_common_substring("zabcy"), "abc")

    def test_no_common(self):
        tools = StringTools("abc")
        self.assertEqual(tools.longest_common_substring("xyz"), "")

    def test_empty_other(self):
        tools = StringTools("abc")
        self.assertEqual(tools.longest_common_substring(""), "")

    def test_all_same(self):
        tools = StringTools("aaaa")
        self.assertEqual(tools.longest_common_substring("aaa"), "aaa")

    def test_identical_texts(self):
        tools = StringTools("hash")
        self.assertEqual(tools.longest_common_substring("hash"), "hash")


class TestErrors(unittest.TestCase):
    def test_non_string_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools(123)

    def test_non_string_other_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools("abc").longest_common_substring(5)

    def test_negative_start_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools("abc").equal(-1, 1, 0, 2)

    def test_end_beyond_length_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools("abc").equal(0, 4, 0, 1)

    def test_reversed_range_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools("abc").equal(2, 1, 0, 1)

    def test_non_integer_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            StringTools("abc").equal(0, 1.5, 0, 1)

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidInputError, HashxError))
        self.assertTrue(issubclass(HashxError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_result(self):
        tools = StringTools("banana")
        self.assertEqual(tools.longest_repeat(), tools.longest_repeat())

    def test_text_unchanged(self):
        tools = StringTools("banana")
        tools.longest_repeat()
        tools.longest_palindrome()
        self.assertEqual(tools.text(), "banana")


if __name__ == "__main__":
    unittest.main()
