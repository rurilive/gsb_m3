"""Baseline tests for the flat bitmap.

These tests lock down the naive per-bit behaviour.  They must stay green and
must not be edited by the interval-tree work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bitrange import BitError, FlatBits


class FlatBitsBasicsTest(unittest.TestCase):
    def test_starts_all_zero(self):
        bits = FlatBits(8)
        self.assertEqual(bits.size, 8)
        self.assertEqual([bits.get(i) for i in range(8)], [0] * 8)
        self.assertTrue(bits.is_all_zero(0, 8))

    def test_size_zero(self):
        bits = FlatBits(0)
        self.assertEqual(bits.size, 0)
        self.assertEqual(bits.count_all_one(), 0)

    def test_negative_size_rejected(self):
        with self.assertRaises(BitError):
            FlatBits(-1)

    def test_non_int_size_rejected(self):
        with self.assertRaises(TypeError):
            FlatBits(4.0)


class FlatBitsSetClearTest(unittest.TestCase):
    def test_set_and_clear_single_bits(self):
        bits = FlatBits(5)
        bits.set(1)
        bits.set(3)
        self.assertEqual([bits.get(i) for i in range(5)], [0, 1, 0, 1, 0])
        bits.clear(1)
        self.assertEqual([bits.get(i) for i in range(5)], [0, 0, 0, 1, 0])

    def test_index_out_of_range(self):
        bits = FlatBits(3)
        with self.assertRaises(BitError):
            bits.set(3)
        with self.assertRaises(BitError):
            bits.get(-1)


class FlatBitsRangeTest(unittest.TestCase):
    def setUp(self):
        self.bits = FlatBits(6)
        for index in (1, 2, 4):
            self.bits.set(index)

    def test_is_all_one_scans_span(self):
        self.assertTrue(self.bits.is_all_one(1, 3))
        self.assertFalse(self.bits.is_all_one(1, 4))

    def test_is_all_zero_scans_span(self):
        self.assertTrue(self.bits.is_all_zero(5, 6))
        self.assertFalse(self.bits.is_all_zero(2, 4))

    def test_empty_span_is_vacuously_true(self):
        self.assertTrue(self.bits.is_all_one(2, 2))
        self.assertTrue(self.bits.is_all_zero(2, 2))

    def test_count_one_in_span(self):
        self.assertEqual(self.bits.count_one(1, 5), 3)
        self.assertEqual(self.bits.count_all_one(), 3)

    def test_invalid_span_rejected(self):
        with self.assertRaises(BitError):
            self.bits.is_all_one(4, 2)
        with self.assertRaises(BitError):
            self.bits.count_one(0, 7)


class FlatBitsFindTest(unittest.TestCase):
    def test_find_next_zero(self):
        bits = FlatBits(6)
        for index in (0, 1, 3):
            bits.set(index)
        self.assertEqual(bits.find_next_zero(0), 2)
        self.assertEqual(bits.find_next_zero(1), 2)
        self.assertEqual(bits.find_next_zero(2), 2)
        self.assertEqual(bits.find_next_zero(4), 4)

    def test_find_next_zero_none_left(self):
        bits = FlatBits(3)
        for index in range(3):
            bits.set(index)
        self.assertEqual(bits.find_next_zero(0), -1)

    def test_find_next_one(self):
        bits = FlatBits(6)
        for index in (2, 5):
            bits.set(index)
        self.assertEqual(bits.find_next_one(0), 2)
        self.assertEqual(bits.find_next_one(3), 5)
        self.assertEqual(bits.find_next_one(5), 5)


if __name__ == "__main__":
    unittest.main()
