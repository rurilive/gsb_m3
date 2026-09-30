"""SeqAlign 现有行为的锁定测试。"""

import unittest

from seqalign.core import (
    EmptyInputError,
    SeqAlign,
    SeqAlignError,
    TypeMismatchError,
)


class TestLcsLength(unittest.TestCase):
    def setUp(self):
        self.s = SeqAlign()

    def test_identical(self):
        self.assertEqual(self.s.lcs_length("abc", "abc"), 3)

    def test_disjoint(self):
        self.assertEqual(self.s.lcs_length("abc", "xyz"), 0)

    def test_partial(self):
        self.assertEqual(self.s.lcs_length("abcde", "ace"), 3)

    def test_empty_pair(self):
        self.assertEqual(self.s.lcs_length("", ""), 0)

    def test_one_empty(self):
        self.assertEqual(self.s.lcs_length("abc", ""), 0)

    def test_single_char(self):
        self.assertEqual(self.s.lcs_length("a", "a"), 1)
        self.assertEqual(self.s.lcs_length("a", "b"), 0)

    def test_repeated_chars(self):
        self.assertEqual(self.s.lcs_length("aaab", "aab"), 3)

    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            self.s.lcs_length(b"abc", "abc")


class TestLcsString(unittest.TestCase):
    def setUp(self):
        self.s = SeqAlign()

    def test_returns_common_subsequence(self):
        sub = self.s.lcs_string("abcde", "ace")
        self.assertEqual(len(sub), 3)
        self.assertEqual(sub, "ace")

    def test_empty_when_disjoint(self):
        self.assertEqual(self.s.lcs_string("abc", "xyz"), "")

    def test_is_subsequence_of_both(self):
        sub = self.s.lcs_string("aggtab", "gxtxayb")

        def is_sub(small, big):
            it = iter(big)
            return all(c in it for c in small)

        self.assertTrue(is_sub(sub, "aggtab"))
        self.assertTrue(is_sub(sub, "gxtxayb"))


class TestEditDistance(unittest.TestCase):
    def setUp(self):
        self.s = SeqAlign()

    def test_known(self):
        self.assertEqual(self.s.edit_distance("kitten", "sitting"), 3)

    def test_identical(self):
        self.assertEqual(self.s.edit_distance("abc", "abc"), 0)

    def test_empty_pair(self):
        self.assertEqual(self.s.edit_distance("", ""), 0)

    def test_one_empty(self):
        self.assertEqual(self.s.edit_distance("abc", ""), 3)

    def test_all_different(self):
        self.assertEqual(self.s.edit_distance("abc", "xyz"), 3)

    def test_repeated_chars(self):
        self.assertEqual(self.s.edit_distance("aaab", "aab"), 1)

    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            self.s.edit_distance("abc", 5)


class TestIndelDistance(unittest.TestCase):
    def setUp(self):
        self.s = SeqAlign()

    def test_identity_formula(self):
        a, b = "abcde", "ace"
        self.assertEqual(
            self.s.indel_distance(a, b),
            len(a) + len(b) - 2 * self.s.lcs_length(a, b),
        )

    def test_empty_pair(self):
        self.assertEqual(self.s.indel_distance("", ""), 0)

    def test_one_empty(self):
        self.assertEqual(self.s.indel_distance("abc", ""), 3)

    def test_identical(self):
        self.assertEqual(self.s.indel_distance("abcd", "abcd"), 0)


class TestCommonSubstringAndPrefix(unittest.TestCase):
    def setUp(self):
        self.s = SeqAlign()

    def test_substring_length(self):
        self.assertEqual(self.s.lcs_substring("abcde", "xbcdz"), 3)

    def test_substring_none(self):
        self.assertEqual(self.s.lcs_substring("abc", "xyz"), 0)

    def test_substring_empty(self):
        self.assertEqual(self.s.lcs_substring("", "abc"), 0)

    def test_prefix(self):
        self.assertEqual(self.s.lcs_prefix("abcdef", "abcxyz"), 3)

    def test_prefix_all(self):
        self.assertEqual(self.s.lcs_prefix("abc", "abc"), 3)

    def test_prefix_none(self):
        self.assertEqual(self.s.lcs_prefix("abc", "xyz"), 0)

    def test_prefix_one_empty(self):
        self.assertEqual(self.s.lcs_prefix("", "abc"), 0)


class TestErrorsShareOneRoot(unittest.TestCase):
    def test_subclasses(self):
        self.assertTrue(issubclass(TypeMismatchError, SeqAlignError))
        self.assertTrue(issubclass(EmptyInputError, SeqAlignError))


if __name__ == "__main__":
    unittest.main()
