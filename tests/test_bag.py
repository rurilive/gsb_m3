"""基线测试：锁住 SortedBag 现有的朴素行为。

这里只验证改造前的既有口径，不涉及任何新能力。改造时本文件
一字不能改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splayx.btree import SortedBag, BagError


class TestInit(unittest.TestCase):
    def test_empty_by_default(self):
        self.assertEqual(len(SortedBag()), 0)
        self.assertEqual(SortedBag().to_list(), [])

    def test_from_iterable_is_sorted(self):
        self.assertEqual(SortedBag([5, 1, 3, 2]).to_list(), [1, 2, 3, 5])

    def test_from_iterable_keeps_duplicates(self):
        self.assertEqual(SortedBag([3, 1, 3, 1]).to_list(), [1, 1, 3, 3])


class TestContains(unittest.TestCase):
    def test_present_and_absent(self):
        s = SortedBag([1, 2, 4])
        self.assertIn(2, s)
        self.assertNotIn(3, s)

    def test_empty(self):
        self.assertNotIn(1, SortedBag())


class TestInsert(unittest.TestCase):
    def test_insert_keeps_order(self):
        s = SortedBag()
        for x in [3, 1, 2, 5, 4]:
            s.insert(x)
        self.assertEqual(s.to_list(), [1, 2, 3, 4, 5])

    def test_insert_duplicates(self):
        s = SortedBag([2, 2])
        s.insert(2)
        self.assertEqual(s.to_list(), [2, 2, 2])
        self.assertEqual(len(s), 3)

    def test_insert_equal_goes_after_existing(self):
        s = SortedBag([2])
        s.insert(2)
        self.assertEqual(s.to_list(), [2, 2])


class TestRemove(unittest.TestCase):
    def test_remove_present(self):
        s = SortedBag([1, 2, 3])
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 3])

    def test_remove_one_of_duplicates(self):
        s = SortedBag([1, 2, 2, 3])
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 2, 3])

    def test_remove_missing_raises_bagerror(self):
        s = SortedBag([1, 3])
        with self.assertRaises(BagError):
            s.remove(2)

    def test_remove_from_empty_raises_bagerror(self):
        with self.assertRaises(BagError):
            SortedBag().remove(1)

    def test_insert_then_remove_returns_to_start(self):
        s = SortedBag([1, 3])
        s.insert(2)
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 3])


class TestFind(unittest.TestCase):
    def test_find_present_returns_element(self):
        s = SortedBag([1, 2, 2, 3])
        self.assertEqual(s.find(2), 2)

    def test_find_absent_returns_none(self):
        self.assertIsNone(SortedBag([1, 3]).find(2))
        self.assertIsNone(SortedBag().find(1))


class TestKth(unittest.TestCase):
    def test_kth_returns_sorted_element(self):
        s = SortedBag([4, 1, 3, 2])
        self.assertEqual(s.kth(0), 1)
        self.assertEqual(s.kth(1), 2)
        self.assertEqual(s.kth(2), 3)
        self.assertEqual(s.kth(3), 4)

    def test_kth_with_duplicates(self):
        s = SortedBag([2, 1, 2])
        self.assertEqual(s.kth(0), 1)
        self.assertEqual(s.kth(1), 2)
        self.assertEqual(s.kth(2), 2)

    def test_kth_out_of_range_raises_bagerror(self):
        s = SortedBag([1, 2])
        with self.assertRaises(BagError):
            s.kth(2)
        with self.assertRaises(BagError):
            s.kth(-1)

    def test_kth_on_empty_raises_bagerror(self):
        with self.assertRaises(BagError):
            SortedBag().kth(0)


class TestRank(unittest.TestCase):
    def test_rank_counts_strictly_smaller(self):
        s = SortedBag([1, 2, 2, 4])
        self.assertEqual(s.rank(1), 0)
        self.assertEqual(s.rank(2), 1)
        self.assertEqual(s.rank(3), 3)
        self.assertEqual(s.rank(5), 4)

    def test_rank_on_empty(self):
        self.assertEqual(SortedBag().rank(10), 0)

    def test_rank_below_all(self):
        self.assertEqual(SortedBag([5, 6]).rank(0), 0)


class TestPredecessorSuccessor(unittest.TestCase):
    def test_predecessor(self):
        s = SortedBag([1, 3, 3, 7])
        self.assertEqual(s.predecessor(3), 1)
        self.assertEqual(s.predecessor(7), 3)
        self.assertIsNone(s.predecessor(1))
        self.assertIsNone(s.predecessor(0))

    def test_successor(self):
        s = SortedBag([1, 3, 3, 7])
        self.assertEqual(s.successor(1), 3)
        self.assertEqual(s.successor(3), 7)
        self.assertIsNone(s.successor(7))
        self.assertIsNone(s.successor(8))

    def test_on_empty(self):
        s = SortedBag()
        self.assertIsNone(s.predecessor(5))
        self.assertIsNone(s.successor(5))


class TestCountRange(unittest.TestCase):
    def test_closed_interval(self):
        s = SortedBag([1, 2, 3, 4, 5])
        self.assertEqual(s.count_range(2, 4), 3)
        self.assertEqual(s.count_range(1, 5), 5)

    def test_bounds_inclusive(self):
        s = SortedBag([1, 2, 2, 3])
        self.assertEqual(s.count_range(2, 2), 2)

    def test_empty_interval(self):
        s = SortedBag([1, 3])
        self.assertEqual(s.count_range(2, 2), 0)

    def test_inverted_range_is_zero(self):
        s = SortedBag([1, 2, 3])
        self.assertEqual(s.count_range(3, 1), 0)

    def test_range_on_empty(self):
        self.assertEqual(SortedBag().count_range(0, 10), 0)


class TestInorder(unittest.TestCase):
    def test_inorder_is_sorted(self):
        s = SortedBag([5, 1, 4, 4, 2, 8])
        self.assertEqual(s.inorder(), [1, 2, 4, 4, 5, 8])

    def test_inorder_on_empty(self):
        self.assertEqual(SortedBag().inorder(), [])


class TestAgainstBruteforce(unittest.TestCase):
    def test_state_equals_naive_sorted_list(self):
        s = SortedBag()
        data = [5, 3, 9, 1, 3, 7, 3, 0]
        for x in data:
            s.insert(x)
        self.assertEqual(s.to_list(), sorted(data))

    def test_ranking_matches_bruteforce(self):
        s = SortedBag([5, 1, 4, 4, 2])
        brute = sorted([5, 1, 4, 4, 2])
        for v in range(0, 7):
            self.assertEqual(s.rank(v), len([y for y in brute if y < v]))

    def test_count_range_matches_bruteforce(self):
        s = SortedBag([1, 2, 2, 3, 5, 8])
        brute = [1, 2, 2, 3, 5, 8]
        for lo in range(0, 10):
            for hi in range(0, 10):
                expected = len([y for y in brute if lo <= y <= hi])
                self.assertEqual(s.count_range(lo, hi), expected)

    def test_delete_all_leaves_empty(self):
        s = SortedBag([3, 1, 2, 2])
        for x in [1, 2, 2, 3]:
            s.remove(x)
        self.assertEqual(s.to_list(), [])
        self.assertEqual(len(s), 0)


if __name__ == "__main__":
    unittest.main()
