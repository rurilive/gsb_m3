"""基线测试: 锁住 FlatXor 当前的线性扫描行为, 必须一直全绿。"""

import unittest

from xorlib.xor import FlatXor


class AddAndLenTest(unittest.TestCase):
    def test_empty(self):
        s = FlatXor()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.values(), [])

    def test_add_appends(self):
        s = FlatXor()
        s.add(5)
        s.add(1)
        s.add(5)
        self.assertEqual(len(s), 3)
        self.assertEqual(s.values(), [5, 1, 5])

    def test_contains(self):
        s = FlatXor()
        s.add(3)
        self.assertIn(3, s)
        self.assertNotIn(4, s)

    def test_add_rejects_non_int(self):
        s = FlatXor()
        with self.assertRaises(ValueError):
            s.add(1.5)
        with self.assertRaises(ValueError):
            s.add(True)


class MaxMinXorTest(unittest.TestCase):
    def test_max_xor_picks_best(self):
        s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            s.add(v)
        # 25 ^ 8 = 17 是最大
        self.assertEqual(s.max_xor(8), 25)

    def test_min_xor_picks_best(self):
        s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            s.add(v)
        # 5 ^ 7 = 2 是最小
        self.assertEqual(s.min_xor(7), 5)

    def test_max_xor_exact_match(self):
        s = FlatXor()
        s.add(7)
        s.add(7)
        self.assertEqual(s.max_xor(7), 7)
        self.assertEqual(s.min_xor(7), 7)

    def test_empty_raises(self):
        s = FlatXor()
        with self.assertRaises(ValueError):
            s.max_xor(1)
        with self.assertRaises(ValueError):
            s.min_xor(1)


class CountLeTest(unittest.TestCase):
    def test_count_le_basic(self):
        s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            s.add(v)
        self.assertEqual(s.count_le(4), 2)
        self.assertEqual(s.count_le(25), 6)
        self.assertEqual(s.count_le(1), 0)
        self.assertEqual(s.count_le(50), 6)


class MaxXorPairTest(unittest.TestCase):
    def test_pair(self):
        s = FlatXor()
        for v in (3, 10, 5, 25, 2, 8):
            s.add(v)
        # 25 ^ 5 = 28 是最大
        self.assertEqual(s.max_xor_pair(), 28)

    def test_pair_two_elements(self):
        s = FlatXor()
        s.add(1)
        s.add(2)
        self.assertEqual(s.max_xor_pair(), 3)

    def test_pair_too_few_raises(self):
        s = FlatXor()
        s.add(1)
        with self.assertRaises(ValueError):
            s.max_xor_pair()


if __name__ == "__main__":
    unittest.main()
