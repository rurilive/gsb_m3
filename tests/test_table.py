"""NaiveSuffix 现有行为的锁定测试（基线，不许改）。"""

import unittest

from suffixx.table import IndexError_, NaiveSuffix, SuffixError


class TestConstruction(unittest.TestCase):
    def test_len_and_text(self):
        t = NaiveSuffix("banana")
        self.assertEqual(len(t), 6)
        self.assertEqual(t.text, "banana")

    def test_empty_text(self):
        t = NaiveSuffix("")
        self.assertEqual(len(t), 0)
        self.assertEqual(t.suffixes(), [])

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSuffix(b"bytes")


class TestSuffixes(unittest.TestCase):
    def test_banana_order(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.suffixes(), [5, 3, 1, 0, 4, 2])

    def test_single_char(self):
        self.assertEqual(NaiveSuffix("a").suffixes(), [0])

    def test_sorted_and_complete(self):
        t = NaiveSuffix("mississippi")
        order = t.suffixes()
        self.assertEqual(sorted(order), list(range(len(t))))
        texts = [t.text[i:] for i in order]
        self.assertEqual(texts, sorted(texts))

    def test_all_equal_chars(self):
        t = NaiveSuffix("aaaa")
        self.assertEqual(t.suffixes(), [3, 2, 1, 0])


class TestCountDistinctSubstrings(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(NaiveSuffix("banana").count_distinct_substrings(), 15)

    def test_single_char(self):
        self.assertEqual(NaiveSuffix("a").count_distinct_substrings(), 1)

    def test_empty(self):
        self.assertEqual(NaiveSuffix("").count_distinct_substrings(), 0)

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSuffix("aaaa").count_distinct_substrings(), 4)

    def test_abab(self):
        self.assertEqual(NaiveSuffix("abab").count_distinct_substrings(), 7)


class TestLongestCommonPrefixOfSuffixes(unittest.TestCase):
    def test_same_index(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.longest_common_prefix_of_suffixes(1, 1), 5)

    def test_banana_pair(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.longest_common_prefix_of_suffixes(1, 3), 3)

    def test_no_common_prefix(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.longest_common_prefix_of_suffixes(0, 2), 0)

    def test_out_of_range(self):
        t = NaiveSuffix("abc")
        with self.assertRaises(IndexError_):
            t.longest_common_prefix_of_suffixes(0, 3)

    def test_error_is_suffix_error(self):
        t = NaiveSuffix("abc")
        with self.assertRaises(SuffixError):
            t.longest_common_prefix_of_suffixes(-1, 0)


class TestFind(unittest.TestCase):
    def test_internal_occurrences(self):
        self.assertEqual(NaiveSuffix("banana").find("ana"), [1, 3])

    def test_missing(self):
        self.assertEqual(NaiveSuffix("banana").find("xyz"), [])

    def test_pattern_longer_than_text(self):
        self.assertEqual(NaiveSuffix("ab").find("abc"), [])

    def test_empty_pattern(self):
        self.assertEqual(NaiveSuffix("abc").find(""), [0, 1, 2, 3])

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSuffix("abc").find(1)


if __name__ == "__main__":
    unittest.main()
