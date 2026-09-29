"""FlatSorted 现有行为的锁定基线。

这份测试锁住改造前的朴素有序 list 语义，跳表改造之后必须一字不改且仍然全绿。
"""

import unittest

from skiplib.sorted import FlatSorted


class TestFlatSortedAdd(unittest.TestCase):
    def test_add_returns_true_for_new(self):
        s = FlatSorted()
        self.assertTrue(s.add(3))
        self.assertEqual(len(s), 1)

    def test_add_idempotent_duplicate(self):
        s = FlatSorted()
        self.assertTrue(s.add(1))
        self.assertFalse(s.add(1))
        self.assertEqual(len(s), 1)

    def test_add_keeps_sorted(self):
        s = FlatSorted()
        for x in (5, 1, 4, 2, 3):
            s.add(x)
        self.assertEqual(s.range_query(1, 5), [1, 2, 3, 4, 5])

    def test_add_none_rejected(self):
        s = FlatSorted()
        with self.assertRaises(TypeError):
            s.add(None)


class TestFlatSortedContains(unittest.TestCase):
    def test_contains_hit_and_miss(self):
        s = FlatSorted()
        for x in (2, 4, 6):
            s.add(x)
        self.assertTrue(s.contains(4))
        self.assertFalse(s.contains(5))

    def test_contains_empty(self):
        s = FlatSorted()
        self.assertFalse(s.contains(0))


class TestFlatSortedDiscard(unittest.TestCase):
    def test_discard_removes_one(self):
        s = FlatSorted()
        for x in (1, 2, 3):
            s.add(x)
        self.assertTrue(s.discard(2))
        self.assertEqual(s.range_query(1, 3), [1, 3])
        self.assertEqual(len(s), 2)

    def test_discard_missing_returns_false(self):
        s = FlatSorted()
        s.add(1)
        self.assertFalse(s.discard(9))
        self.assertEqual(len(s), 1)


class TestFlatSortedRankKth(unittest.TestCase):
    def test_rank_counts_less_than(self):
        s = FlatSorted()
        for x in (10, 20, 30):
            s.add(x)
        self.assertEqual(s.rank(20), 1)
        self.assertEqual(s.rank(10), 0)
        self.assertEqual(s.rank(31), 3)

    def test_kth_zero_based(self):
        s = FlatSorted()
        for x in (30, 10, 20):
            s.add(x)
        self.assertEqual(s.kth(0), 10)
        self.assertEqual(s.kth(1), 20)
        self.assertEqual(s.kth(2), 30)

    def test_kth_out_of_range(self):
        s = FlatSorted()
        s.add(1)
        with self.assertRaises(ValueError):
            s.kth(1)
        with self.assertRaises(ValueError):
            s.kth(-1)


class TestFlatSortedRange(unittest.TestCase):
    def test_range_query_closed_interval(self):
        s = FlatSorted()
        for x in (1, 2, 3, 4, 5):
            s.add(x)
        self.assertEqual(s.range_query(2, 4), [2, 3, 4])
        self.assertEqual(s.range_query(1, 5), [1, 2, 3, 4, 5])

    def test_range_query_empty(self):
        s = FlatSorted()
        s.add(1)
        s.add(2)
        self.assertEqual(s.range_query(3, 9), [])
        self.assertEqual(s.range_query(2, 1), [])


class TestFlatSortedEdges(unittest.TestCase):
    def test_empty_len(self):
        s = FlatSorted()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.range_query(0, 9), [])
        self.assertEqual(s.rank(5), 0)

    def test_all_equal_sequence(self):
        s = FlatSorted()
        for _ in range(3):
            s.add(7)
        self.assertEqual(len(s), 1)
        self.assertEqual(s.kth(0), 7)


if __name__ == "__main__":
    unittest.main()
