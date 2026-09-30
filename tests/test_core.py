"""基线测试：锁住 EditPath 朴素实现的现状行为。

这些用例全部基于很短的串，保证朴素递归与枚举能在瞬间跑完；用例断言的是
结果本身，不涉及任何内部状态或模块级缓存。改造时本文件一个字不许改。
"""

import unittest

from editpath.core import EditPath, EditPathError, TypeMismatchError


class TestEditDistance(unittest.TestCase):
    def setUp(self):
        self.ep = EditPath()

    def test_empty_both(self):
        self.assertEqual(self.ep.edit_distance("", ""), 0)

    def test_first_empty(self):
        self.assertEqual(self.ep.edit_distance("", "abc"), 3)

    def test_second_empty(self):
        self.assertEqual(self.ep.edit_distance("abc", ""), 3)

    def test_same_string(self):
        self.assertEqual(self.ep.edit_distance("kitten", "kitten"), 0)

    def test_kitten_sitting(self):
        self.assertEqual(self.ep.edit_distance("kitten", "sitting"), 3)

    def test_single_char(self):
        self.assertEqual(self.ep.edit_distance("a", "b"), 1)
        self.assertEqual(self.ep.edit_distance("a", "a"), 0)

    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            self.ep.edit_distance(1, "a")
        with self.assertRaises(TypeMismatchError):
            self.ep.edit_distance("a", None)

    def test_error_base(self):
        self.assertTrue(issubclass(TypeMismatchError, EditPathError))
        self.assertTrue(issubclass(EditPathError, Exception))


class TestWeightedAndIndel(unittest.TestCase):
    def setUp(self):
        self.ep = EditPath()

    def test_weighted_unit(self):
        self.assertEqual(
            self.ep.weighted_distance("kitten", "sitting", 1, 1, 1), 3)

    def test_weighted_delete_heavy(self):
        # 删掉 a 的两个字符再补 b 的字符，退化为只增删时的代价。
        self.assertEqual(
            self.ep.weighted_distance("ab", "cd", 5, 1, 1), 4)

    def test_weighted_zero(self):
        self.assertEqual(
            self.ep.weighted_distance("abc", "xyz", 0, 0, 0), 0)

    def test_weighted_bad(self):
        with self.assertRaises(TypeMismatchError):
            self.ep.weighted_distance("a", "b", -1, 1, 1)

    def test_indel(self):
        self.assertEqual(self.ep.indel_distance("abc", "abc"), 0)
        self.assertEqual(self.ep.indel_distance("abc", "abd"), 2)
        self.assertEqual(self.ep.indel_distance("", "abc"), 3)


class TestLcsAndPrefix(unittest.TestCase):
    def setUp(self):
        self.ep = EditPath()

    def test_lcs_length(self):
        self.assertEqual(self.ep.lcs_length("abcde", "ace"), 3)
        self.assertEqual(self.ep.lcs_length("abc", "xyz"), 0)
        self.assertEqual(self.ep.lcs_length("", "abc"), 0)

    def test_lcs_substring(self):
        self.assertEqual(self.ep.lcs_substring("abcdef", "zabcf"), 3)
        self.assertEqual(self.ep.lcs_substring("abc", "xyz"), 0)

    def test_lcs_prefix(self):
        self.assertEqual(self.ep.lcs_prefix("abcdef", "abcxyz"), 3)
        self.assertEqual(self.ep.lcs_prefix("abc", "abc"), 3)
        self.assertEqual(self.ep.lcs_prefix("", "abc"), 0)


if __name__ == "__main__":
    unittest.main()
