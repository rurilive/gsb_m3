"""BoolBits 现有行为的锁定测试。"""

import unittest

from bitlib.bitset import BitlibError, BoolBits


class TestBoolBits(unittest.TestCase):
    def test_set_and_get(self):
        b = BoolBits(8)
        b.set(3)
        b.set(5)
        self.assertTrue(b.get(3))
        self.assertTrue(b.get(5))
        self.assertFalse(b.get(0))

    def test_clear_turns_bit_off(self):
        b = BoolBits(8)
        b.set(2)
        b.clear(2)
        self.assertFalse(b.get(2))

    def test_count(self):
        b = BoolBits(16)
        for i in (1, 4, 9, 15):
            b.set(i)
        self.assertEqual(b.count(), 4)

    def test_union_and_intersection(self):
        a = BoolBits(8)
        c = BoolBits(8)
        a.set(1)
        a.set(3)
        c.set(3)
        c.set(6)
        u = a.union(c)
        i = a.intersection(c)
        self.assertEqual(u.to_list(), [1, 3, 6])
        self.assertEqual(i.to_list(), [3])

    def test_to_list_is_sorted(self):
        b = BoolBits(10)
        for i in (7, 2, 5):
            b.set(i)
        self.assertEqual(b.to_list(), [2, 5, 7])

    def test_length_must_not_be_negative(self):
        with self.assertRaises(BitlibError):
            BoolBits(-1)

    def test_index_out_of_range(self):
        b = BoolBits(4)
        with self.assertRaises(BitlibError):
            b.set(4)
        with self.assertRaises(BitlibError):
            b.get(-1)

    def test_pair_lengths_must_match(self):
        a = BoolBits(4)
        b = BoolBits(8)
        with self.assertRaises(BitlibError):
            a.union(b)

    def test_equal_when_same_bits(self):
        a = BoolBits(4)
        b = BoolBits(4)
        a.set(2)
        b.set(2)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
