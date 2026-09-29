"""基线测试：锁定 CharDiff 的逐字符比较行为。

这些断言在改造前后都必须成立，改造时不得修改本文件。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nearbex import CharDiff
from nearbex.sim import NearbexError


class TestCharDiffBaseline(unittest.TestCase):

    def test_identical_texts_zero_diff(self):
        self.assertEqual(CharDiff("hello", "hello").diff_count(), 0)

    def test_identical_texts_are_same(self):
        self.assertTrue(CharDiff("hello", "hello").is_same())

    def test_single_position_difference(self):
        self.assertEqual(CharDiff("hello", "hallo").diff_count(), 1)

    def test_all_positions_difference(self):
        self.assertEqual(CharDiff("abc", "xyz").diff_count(), 3)

    def test_length_difference_counts_as_diff(self):
        self.assertEqual(CharDiff("abc", "ab").diff_count(), 1)

    def test_empty_both_sides(self):
        self.assertEqual(CharDiff("", "").diff_count(), 0)

    def test_empty_left_side(self):
        self.assertEqual(CharDiff("", "abc").diff_count(), 3)

    def test_empty_right_side(self):
        self.assertEqual(CharDiff("abc", "").diff_count(), 3)

    def test_different_lengths_not_same(self):
        self.assertFalse(CharDiff("abc", "abcd").is_same())

    def test_case_sensitive(self):
        self.assertEqual(CharDiff("Abc", "abc").diff_count(), 1)

    def test_diff_count_is_int(self):
        self.assertIsInstance(CharDiff("a", "b").diff_count(), int)

    def test_repeated_call_is_stable(self):
        diff = CharDiff("kitten", "sitting")
        self.assertEqual(diff.diff_count(), diff.diff_count())

    def test_attributes_kept_as_given(self):
        diff = CharDiff("left", "right")
        self.assertEqual(diff.left, "left")
        self.assertEqual(diff.right, "right")


class TestNearbexErrorBaseline(unittest.TestCase):

    def test_error_base_is_exception(self):
        self.assertTrue(issubclass(NearbexError, Exception))

    def test_error_can_be_raised_and_caught(self):
        with self.assertRaises(NearbexError):
            raise NearbexError("boom")


if __name__ == "__main__":
    unittest.main()
