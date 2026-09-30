"""NaiveSubstrings 现有行为的锁定测试（基线，不许改）。"""

import unittest

from samx.substrings import Erro, IndexError_, NaiveSubstrings


class TestConstruction(unittest.TestCase):
    def test_len_and_text(self):
        t = NaiveSubstrings("banana")
        self.assertEqual(len(t), 6)
        self.assertEqual(t.text, "banana")

    def test_empty_text(self):
        t = NaiveSubstrings("")
        self.assertEqual(len(t), 0)
        self.assertEqual(t.all_substrings(), [])
        self.assertEqual(t.distinct_substrings(), set())

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSubstrings(b"bytes")


class TestEnumeration(unittest.TestCase):
    def test_all_substrings_count(self):
        self.assertEqual(len(NaiveSubstrings("banana").all_substrings()), 21)

    def test_all_substrings_first(self):
        self.assertEqual(NaiveSubstrings("abc").all_substrings(),
                         ["a", "ab", "abc", "b", "bc", "c"])

    def test_single_char(self):
        self.assertEqual(NaiveSubstrings("a").all_substrings(), ["a"])


class TestDistinct(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(NaiveSubstrings("banana").count_distinct_substrings(), 15)

    def test_abab(self):
        self.assertEqual(NaiveSubstrings("abab").count_distinct_substrings(), 7)

    def test_single_char(self):
        self.assertEqual(NaiveSubstrings("a").count_distinct_substrings(), 1)

    def test_empty(self):
        self.assertEqual(NaiveSubstrings("").count_distinct_substrings(), 0)

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSubstrings("aaaa").count_distinct_substrings(), 4)

    def test_distinct_membership(self):
        d = NaiveSubstrings("banana").distinct_substrings()
        self.assertIn("ana", d)
        self.assertIn("nan", d)
        self.assertNotIn("xyz", d)


class TestIsSubstring(unittest.TestCase):
    def test_present(self):
        self.assertTrue(NaiveSubstrings("banana").is_substring("nan"))

    def test_absent(self):
        self.assertFalse(NaiveSubstrings("banana").is_substring("xyz"))

    def test_empty_pattern(self):
        self.assertTrue(NaiveSubstrings("abc").is_substring(""))

    def test_pattern_longer_than_text(self):
        self.assertFalse(NaiveSubstrings("ab").is_substring("abc"))

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSubstrings("abc").is_substring(1)


class TestCountOccurrences(unittest.TestCase):
    def test_banana_ana(self):
        self.assertEqual(NaiveSubstrings("banana").count_occurrences("ana"), 2)

    def test_banana_a(self):
        self.assertEqual(NaiveSubstrings("banana").count_occurrences("a"), 3)

    def test_missing(self):
        self.assertEqual(NaiveSubstrings("banana").count_occurrences("xyz"), 0)

    def test_pattern_longer_than_text(self):
        self.assertEqual(NaiveSubstrings("ab").count_occurrences("abc"), 0)

    def test_empty_pattern(self):
        self.assertEqual(NaiveSubstrings("abc").count_occurrences(""), 0)

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSubstrings("aaaa").count_occurrences("aa"), 3)


class TestAggregation(unittest.TestCase):
    def test_by_length_banana(self):
        self.assertEqual(
            NaiveSubstrings("banana").count_substrings_by_length(),
            {1: 3, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
        )

    def test_by_length_empty(self):
        self.assertEqual(NaiveSubstrings("").count_substrings_by_length(), {})

    def test_lengths_banana(self):
        self.assertEqual(
            NaiveSubstrings("banana").distinct_substring_lengths(),
            [1, 2, 3, 4, 5, 6],
        )

    def test_lengths_single(self):
        self.assertEqual(NaiveSubstrings("a").distinct_substring_lengths(), [1])


class TestErrorHierarchy(unittest.TestCase):
    def test_index_error_is_erro(self):
        self.assertTrue(issubclass(IndexError_, Erro))

    def test_check_index_rejects_bool(self):
        t = NaiveSubstrings("abc")
        with self.assertRaises(Erro):
            t._check_index(True)


if __name__ == "__main__":
    unittest.main()
