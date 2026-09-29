"""HammDiff 现有行为的锁定测试。"""

import unittest

from editlab.diff import EditError, HammDiff, LengthMismatchError


class TestHammDiff(unittest.TestCase):
    def test_identical(self):
        d = HammDiff()
        self.assertEqual(d.diff_count("abc", "abc"), 0)

    def test_all_different(self):
        d = HammDiff()
        self.assertEqual(d.diff_count("abc", "xyz"), 3)

    def test_partial(self):
        d = HammDiff()
        self.assertEqual(d.diff_count("kitten", "sitten"), 1)
        self.assertEqual(d.diff_count("abcd", "abce"), 1)

    def test_empty(self):
        d = HammDiff()
        self.assertEqual(d.diff_count("", ""), 0)

    def test_length_mismatch_raises(self):
        d = HammDiff()
        with self.assertRaises(LengthMismatchError):
            d.diff_count("abc", "ab")

    def test_mismatch_is_edit_error(self):
        d = HammDiff()
        with self.assertRaises(EditError):
            d.diff_count("a", "ab")

    def test_type_error(self):
        d = HammDiff()
        with self.assertRaises(TypeError):
            d.diff_count(b"abc", "abc")

    def test_common_positions(self):
        d = HammDiff()
        self.assertEqual(d.common_positions("abc", "axc"), [0, 2])
        self.assertEqual(d.common_positions("abc", "xyz"), [])

    def test_common_positions_mismatch(self):
        d = HammDiff()
        with self.assertRaises(LengthMismatchError):
            d.common_positions("abc", "ab")


if __name__ == "__main__":
    unittest.main()
