"""FlatXor 基线行为测试。

锁住改造前的朴素现状: 插入、删除、异或极值、数对异或最大的答案口径。
本文件在改造后一字不许改, 且必须一直全绿。
"""

import unittest

from triex.bits import FlatXor


class TestBasics(unittest.TestCase):
    def test_empty(self):
        s = FlatXor()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.values(), [])

    def test_add_and_len_and_contains(self):
        s = FlatXor()
        for v in (3, 10, 5):
            s.add(v)
        self.assertEqual(len(s), 3)
        self.assertIn(3, s)
        self.assertIn(10, s)
        self.assertNotIn(7, s)

    def test_add_duplicates_kept_by_count(self):
        s = FlatXor()
        s.add(4)
        s.add(4)
        s.add(4)
        self.assertEqual(len(s), 3)

    def test_add_rejects_non_int(self):
        s = FlatXor()
        with self.assertRaises(ValueError):
            s.add("9")
        with self.assertRaises(ValueError):
            s.add(True)
        with self.assertRaises(ValueError):
            s.add(-1)

    def test_values_is_a_copy(self):
        s = FlatXor()
        s.add(1)
        got = s.values()
        got.append(2)
        self.assertEqual(len(s), 1)


class TestRemove(unittest.TestCase):
    def test_remove_one_of_duplicates(self):
        s = FlatXor()
        s.add(6)
        s.add(6)
        s.remove(6)
        self.assertEqual(len(s), 1)
        self.assertIn(6, s)

    def test_remove_absent_raises(self):
        s = FlatXor()
        s.add(1)
        with self.assertRaises(ValueError):
            s.remove(99)


class TestXorExtremes(unittest.TestCase):
    def setUp(self):
        self.s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            self.s.add(v)

    def test_max_xor(self):
        self.assertEqual(self.s.max_xor(8), 25)
        self.assertEqual(self.s.max_xor(0), 25)

    def test_min_xor(self):
        self.assertEqual(self.s.min_xor(8), 8)
        self.assertEqual(self.s.min_xor(0), 2)

    def test_empty_raises(self):
        s = FlatXor()
        with self.assertRaises(ValueError):
            s.max_xor(1)
        with self.assertRaises(ValueError):
            s.min_xor(1)


class TestXorPair(unittest.TestCase):
    def test_pair(self):
        s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            s.add(v)
        self.assertEqual(s.max_xor_pair(), 28)

    def test_pair_needs_two(self):
        s = FlatXor()
        with self.assertRaises(ValueError):
            s.max_xor_pair()
        s.add(7)
        with self.assertRaises(ValueError):
            s.max_xor_pair()

    def test_single_value_pair(self):
        s = FlatXor()
        s.add(7)
        s.add(7)
        self.assertEqual(s.max_xor_pair(), 0)


if __name__ == "__main__":
    unittest.main()
