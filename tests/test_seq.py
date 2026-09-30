"""Selector 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一个固定序列上朴素全排序实现的第几个最小、前几个最小之和、中位数
与两序列中位数，以及查询回放的结果，还有非法排名、空序列、个数越界必须
fail fast。
"""

import unittest

from orderstat.seq import (
    EmptySequenceError,
    OrderStatError,
    RankOutOfRangeError,
    Selector,
)

# 固定序列（含负数与重复值）：
#   下标  0   1   2   3   4   5   6   7   8   9
#   值    7  -3   3  -8   0   5   3  -1  12   3
# 全排序后：[-8, -3, -1, 0, 3, 3, 3, 5, 7, 12]
FIXED_DATA = [7, -3, 3, -8, 0, 5, 3, -1, 12, 3]
FIXED_SORTED = [-8, -3, -1, 0, 3, 3, 3, 5, 7, 12]


def build():
    return Selector(FIXED_DATA)


class TestStructure(unittest.TestCase):
    def test_size(self):
        self.assertEqual(build().size(), 10)

    def test_data_returns_copy(self):
        s = build()
        got = s.data
        got.append(999)
        self.assertEqual(s.data, FIXED_DATA)

    def test_empty_sequence(self):
        s = Selector()
        self.assertEqual(s.size(), 0)

    def test_sorted_copy(self):
        self.assertEqual(build().sorted_copy(), FIXED_SORTED)

    def test_sorted_copy_is_fresh(self):
        s = build()
        got = s.sorted_copy()
        got.append(999)
        self.assertEqual(s.sorted_copy(), FIXED_SORTED)


class TestSelectKth(unittest.TestCase):
    def test_smallest(self):
        self.assertEqual(build().select_kth(0), -8)

    def test_second(self):
        self.assertEqual(build().select_kth(1), -3)

    def test_middle(self):
        self.assertEqual(build().select_kth(4), 3)

    def test_largest(self):
        self.assertEqual(build().select_kth(9), 12)

    def test_all_ranks_match_sorted(self):
        s = build()
        for rank in range(s.size()):
            self.assertEqual(s.select_kth(rank), FIXED_SORTED[rank])

    def test_duplicates_at_ranks(self):
        s = build()
        self.assertEqual(s.select_kth(4), 3)
        self.assertEqual(s.select_kth(5), 3)
        self.assertEqual(s.select_kth(6), 3)

    def test_single_element(self):
        self.assertEqual(Selector([42]).select_kth(0), 42)

    def test_all_equal(self):
        self.assertEqual(Selector([5, 5, 5, 5]).select_kth(3), 5)


class TestSmallestSum(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(build().smallest_sum(0), 0)

    def test_one(self):
        self.assertEqual(build().smallest_sum(1), -8)

    def test_three(self):
        self.assertEqual(build().smallest_sum(3), -12)

    def test_five(self):
        self.assertEqual(build().smallest_sum(5), -9)

    def test_full(self):
        self.assertEqual(build().smallest_sum(10), 21)

    def test_matches_sorted_prefix(self):
        s = build()
        for count in range(s.size() + 1):
            self.assertEqual(s.smallest_sum(count), sum(FIXED_SORTED[:count]))

    def test_zero_on_empty(self):
        self.assertEqual(Selector().smallest_sum(0), 0)

    def test_single(self):
        self.assertEqual(Selector([9]).smallest_sum(1), 9)


class TestMedian(unittest.TestCase):
    def test_even_length_takes_mean(self):
        self.assertEqual(build().median(), 3.0)

    def test_odd_length_takes_middle(self):
        self.assertEqual(Selector([3, 1, 2]).median(), 2)

    def test_single_element(self):
        self.assertEqual(Selector([4]).median(), 4)

    def test_matches_sorted(self):
        ordered = FIXED_SORTED
        expected = (ordered[4] + ordered[5]) / 2
        self.assertEqual(build().median(), expected)


class TestPairwiseMedian(unittest.TestCase):
    def test_two_and_two(self):
        self.assertEqual(Selector([1, 2]).pairwise_median([3, 4]), 2.5)

    def test_against_large_other(self):
        self.assertEqual(build().pairwise_median([100, 200]), 3.0)

    def test_self_empty(self):
        self.assertEqual(Selector().pairwise_median([5]), 5)

    def test_other_empty(self):
        self.assertEqual(Selector([5]).pairwise_median([]), 5)

    def test_both_empty_raises(self):
        with self.assertRaises(EmptySequenceError):
            Selector().pairwise_median([])

    def test_unsorted_inputs(self):
        self.assertEqual(Selector([4, 1, 3]).pairwise_median([2, 0]), 2)

    def test_matches_naive_merge(self):
        s = build()
        other = [9, -5, 6]
        expected = sorted(FIXED_DATA + other)
        n = len(expected)
        want = (
            expected[n // 2]
            if n % 2 == 1
            else (expected[n // 2 - 1] + expected[n // 2]) / 2
        )
        self.assertEqual(s.pairwise_median(other), want)


class TestReplay(unittest.TestCase):
    def test_replay_matches_step_by_step(self):
        queries = [
            ("kth", 4),
            ("smallest", 3),
            ("median",),
            ("pairwise", [3, 9]),
            ("kth", 0),
        ]
        final, results = Selector.replay(FIXED_DATA, queries)
        self.assertEqual(results, [3, -12, 3.0, 3.0, -8])
        self.assertEqual(final, FIXED_DATA)

    def test_replay_does_not_touch_source(self):
        source = list(FIXED_DATA)
        Selector.replay(source, [("kth", 2), ("median",)])
        self.assertEqual(source, FIXED_DATA)

    def test_replay_unknown_query_raises(self):
        with self.assertRaises(OrderStatError):
            Selector.replay(FIXED_DATA, [("nope",)])


class TestBadRanks(unittest.TestCase):
    def test_negative_rank(self):
        with self.assertRaises(RankOutOfRangeError):
            build().select_kth(-1)

    def test_rank_at_size(self):
        with self.assertRaises(RankOutOfRangeError):
            build().select_kth(10)

    def test_rank_beyond_size(self):
        with self.assertRaises(RankOutOfRangeError):
            build().select_kth(99)

    def test_float_rank(self):
        with self.assertRaises(RankOutOfRangeError):
            build().select_kth(1.0)

    def test_negative_count(self):
        with self.assertRaises(RankOutOfRangeError):
            build().smallest_sum(-1)

    def test_count_beyond_size(self):
        with self.assertRaises(RankOutOfRangeError):
            build().smallest_sum(11)

    def test_count_beyond_single(self):
        with self.assertRaises(RankOutOfRangeError):
            Selector([5]).smallest_sum(2)

    def test_empty_select_raises(self):
        with self.assertRaises(EmptySequenceError):
            Selector().select_kth(0)

    def test_empty_median_raises(self):
        with self.assertRaises(EmptySequenceError):
            Selector().median()


class TestErrorHierarchy(unittest.TestCase):
    def test_rank_is_orderstat_error(self):
        self.assertTrue(issubclass(RankOutOfRangeError, OrderStatError))

    def test_empty_is_orderstat_error(self):
        self.assertTrue(issubclass(EmptySequenceError, OrderStatError))

    def test_catch_by_base(self):
        with self.assertRaises(OrderStatError):
            build().select_kth(-1)


if __name__ == "__main__":
    unittest.main()
