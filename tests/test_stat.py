"""基线测试：锁住 SortList 现有的朴素行为。

这里只验证改造前的既有口径，不涉及任何新能力。改造时本文件
一字不能改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ostat.stat import SortList, StatError


class TestInit(unittest.TestCase):
    def test_empty_by_default(self):
        self.assertEqual(len(SortList()), 0)
        self.assertEqual(SortList().to_list(), [])

    def test_from_iterable_is_sorted(self):
        self.assertEqual(SortList([5, 1, 3, 2]).to_list(), [1, 2, 3, 5])

    def test_from_iterable_keeps_duplicates(self):
        self.assertEqual(SortList([3, 1, 3, 1]).to_list(), [1, 1, 3, 3])


class TestContains(unittest.TestCase):
    def test_present_and_absent(self):
        s = SortList([1, 2, 4])
        self.assertIn(2, s)
        self.assertNotIn(3, s)

    def test_empty(self):
        self.assertNotIn(1, SortList())


class TestInsert(unittest.TestCase):
    def test_insert_keeps_order(self):
        s = SortList()
        for x in [3, 1, 2, 5, 4]:
            s.insert(x)
        self.assertEqual(s.to_list(), [1, 2, 3, 4, 5])

    def test_insert_duplicates(self):
        s = SortList([2, 2])
        s.insert(2)
        self.assertEqual(s.to_list(), [2, 2, 2])
        self.assertEqual(len(s), 3)

    def test_insert_equal_goes_after_existing(self):
        s = SortList([2])
        s.insert(2)
        self.assertEqual(s.to_list(), [2, 2])


class TestRemove(unittest.TestCase):
    def test_remove_present(self):
        s = SortList([1, 2, 3])
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 3])

    def test_remove_one_of_duplicates(self):
        s = SortList([1, 2, 2, 3])
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 2, 3])

    def test_remove_missing_raises_keyerror(self):
        s = SortList([1, 3])
        with self.assertRaises(KeyError):
            s.remove(2)

    def test_remove_from_empty_raises_keyerror(self):
        with self.assertRaises(KeyError):
            SortList().remove(1)

    def test_insert_then_remove_returns_to_start(self):
        s = SortList([1, 3])
        s.insert(2)
        s.remove(2)
        self.assertEqual(s.to_list(), [1, 3])


class TestKth(unittest.TestCase):
    def test_kth_returns_sorted_element(self):
        s = SortList([4, 1, 3, 2])
        self.assertEqual(s.kth(0), 1)
        self.assertEqual(s.kth(1), 2)
        self.assertEqual(s.kth(2), 3)
        self.assertEqual(s.kth(3), 4)

    def test_kth_with_duplicates(self):
        s = SortList([2, 1, 2])
        self.assertEqual(s.kth(0), 1)
        self.assertEqual(s.kth(1), 2)
        self.assertEqual(s.kth(2), 2)

    def test_kth_out_of_range_raises_staterror(self):
        s = SortList([1, 2])
        with self.assertRaises(StatError):
            s.kth(2)
        with self.assertRaises(StatError):
            s.kth(-1)

    def test_kth_on_empty_raises_staterror(self):
        with self.assertRaises(StatError):
            SortList().kth(0)


class TestRank(unittest.TestCase):
    def test_rank_counts_strictly_smaller(self):
        s = SortList([1, 2, 2, 4])
        self.assertEqual(s.rank(1), 0)
        self.assertEqual(s.rank(2), 1)
        self.assertEqual(s.rank(3), 3)
        self.assertEqual(s.rank(5), 4)

    def test_rank_on_empty(self):
        self.assertEqual(SortList().rank(10), 0)

    def test_rank_below_all(self):
        self.assertEqual(SortList([5, 6]).rank(0), 0)


class TestCountRange(unittest.TestCase):
    def test_closed_interval(self):
        s = SortList([1, 2, 3, 4, 5])
        self.assertEqual(s.count_range(2, 4), 3)
        self.assertEqual(s.count_range(1, 5), 5)

    def test_bounds_inclusive(self):
        s = SortList([1, 2, 2, 3])
        self.assertEqual(s.count_range(2, 2), 2)

    def test_empty_interval(self):
        s = SortList([1, 3])
        self.assertEqual(s.count_range(2, 2), 0)

    def test_inverted_range_is_zero(self):
        s = SortList([1, 2, 3])
        self.assertEqual(s.count_range(3, 1), 0)

    def test_range_on_empty(self):
        self.assertEqual(SortList().count_range(0, 10), 0)


class TestToDictAndToEquals(unittest.TestCase):
    def test_state_equals_naive_sorted_list(self):
        s = SortList()
        data = [5, 3, 9, 1, 3, 7, 3, 0]
        for x in data:
            s.insert(x)
        self.assertEqual(s.to_list(), sorted(data))

    def test_ranking_matches_bruteforce(self):
        s = SortList([5, 1, 4, 4, 2])
        brute = sorted([5, 1, 4, 4, 2])
        for v in range(0, 7):
            self.assertEqual(s.rank(v), len([y for y in brute if y < v]))

    def test_count_range_matches_bruteforce(self):
        s = SortList([1, 2, 2, 3, 5, 8])
        brute = [1, 2, 2, 3, 5, 8]
        for l in range(0, 10):
            for r in range(0, 10):
                expected = len([y for y in brute if l <= y <= r])
                self.assertEqual(s.count_range(l, r), expected)


if __name__ == "__main__":
    unittest.main()
