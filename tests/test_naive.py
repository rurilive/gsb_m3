"""triplet 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与规范、两种口径的三元组计数、
存在性判定与首个三元组、长度四的提升子序列计数、边界与异常层级、
固定输入的可重复性。改造时本文件一个字都不许改，
新行为一律另开测试文件。
"""

import unittest

from triplet.naive import (
    InvalidInputError,
    InvalidLengthError,
    TripletAnalysis,
    TripletError,
    count_increasing_subseq_of_length_naive,
    count_increasing_triplets_naive,
    count_non_decreasing_triplets_naive,
    enumerate_triplet_trials,
    first_increasing_triplet_naive,
    has_increasing_triplet_naive,
)


class TestInputValidation(unittest.TestCase):
    def test_empty_is_allowed(self):
        self.assertEqual(count_increasing_triplets_naive([]), 0)

    def test_non_iterable_raises(self):
        with self.assertRaises(InvalidInputError):
            count_increasing_triplets_naive(3)

    def test_string_raises(self):
        with self.assertRaises(InvalidInputError):
            count_increasing_triplets_naive("123")

    def test_float_raises(self):
        with self.assertRaises(InvalidInputError):
            count_increasing_triplets_naive([1, 2.5])

    def test_bool_is_not_integer(self):
        with self.assertRaises(InvalidInputError):
            count_increasing_triplets_naive([1, True, 3])

    def test_negative_int_allowed(self):
        self.assertEqual(count_increasing_triplets_naive([-2, -1, 0]), 1)


class TestStrictTripletCount(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(count_increasing_triplets_naive([]), 0)

    def test_single(self):
        self.assertEqual(count_increasing_triplets_naive([7]), 0)

    def test_two(self):
        self.assertEqual(count_increasing_triplets_naive([1, 2]), 0)

    def test_ascending(self):
        self.assertEqual(count_increasing_triplets_naive([1, 2, 3, 4]), 4)

    def test_descending(self):
        self.assertEqual(count_increasing_triplets_naive([4, 3, 2, 1]), 0)

    def test_all_equal(self):
        self.assertEqual(count_increasing_triplets_naive([3, 3, 3, 3]), 0)

    def test_mixed_with_duplicates(self):
        self.assertEqual(count_increasing_triplets_naive([2, 4, 1, 3, 5]), 3)

    def test_duplicates_split_two_modes(self):
        self.assertEqual(count_increasing_triplets_naive([1, 1, 2]), 0)
        self.assertEqual(count_non_decreasing_triplets_naive([1, 1, 2]), 1)


class TestNonDecreasingTripletCount(unittest.TestCase):
    def test_ascending(self):
        self.assertEqual(count_non_decreasing_triplets_naive([1, 2, 3, 4]), 4)

    def test_descending(self):
        self.assertEqual(count_non_decreasing_triplets_naive([4, 3, 2, 1]), 0)

    def test_all_equal(self):
        self.assertEqual(count_non_decreasing_triplets_naive([3, 3, 3, 3]), 4)

    def test_two_pairs(self):
        self.assertEqual(count_non_decreasing_triplets_naive([1, 1, 2, 2]), 4)

    def test_strict_never_exceeds_non_decreasing(self):
        data = [2, 4, 1, 3, 5]
        self.assertLessEqual(
            count_increasing_triplets_naive(data),
            count_non_decreasing_triplets_naive(data),
        )


class TestExistenceAndFirst(unittest.TestCase):
    def test_has_on_ascending(self):
        self.assertTrue(has_increasing_triplet_naive([1, 2, 3]))

    def test_has_on_none(self):
        self.assertFalse(has_increasing_triplet_naive([3, 2, 1]))

    def test_has_zero_iff_no_count(self):
        for data in ([1, 2, 3, 4], [4, 3, 2, 1], [2, 4, 1, 3, 5], [3, 3, 3]):
            expected = count_increasing_triplets_naive(data) > 0
            self.assertEqual(has_increasing_triplet_naive(data), expected)

    def test_first_matches_smallest_lexicographic(self):
        self.assertEqual(first_increasing_triplet_naive([3, 1, 4, 1, 5, 9, 2, 6]), (0, 2, 4))

    def test_first_absent(self):
        self.assertIsNone(first_increasing_triplet_naive([5, 4, 3, 2, 1]))

    def test_first_is_valid(self):
        data = [1, 2, 3, 4]
        i, j, k = first_increasing_triplet_naive(data)
        self.assertTrue(i < j < k)
        self.assertTrue(data[i] < data[j] < data[k])


class TestLengthFourSubsequence(unittest.TestCase):
    def test_ascending(self):
        self.assertEqual(
            count_increasing_subseq_of_length_naive([1, 2, 3, 4], 4), 1
        )

    def test_too_short(self):
        self.assertEqual(
            count_increasing_subseq_of_length_naive([1, 2, 3], 4), 0
        )

    def test_all_equal_strict(self):
        self.assertEqual(
            count_increasing_subseq_of_length_naive([3, 3, 3, 3], 4), 0
        )

    def test_all_equal_non_decreasing(self):
        self.assertEqual(
            count_increasing_subseq_of_length_naive([3, 3, 3, 3], 4, strict=False), 1
        )

    def test_longer_ascending(self):
        self.assertEqual(
            count_increasing_subseq_of_length_naive([1, 2, 3, 4, 5], 4), 5
        )

    def test_bad_length_raises(self):
        with self.assertRaises(InvalidLengthError):
            count_increasing_subseq_of_length_naive([1, 2, 3], 1)


class TestTrialAccounting(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(enumerate_triplet_trials([]), 0)

    def test_small(self):
        self.assertEqual(enumerate_triplet_trials([1, 2, 3]), 1)

    def test_matches_choose_three(self):
        data = [0] * 5
        self.assertEqual(enumerate_triplet_trials(data), 10)


class TestAnalysisFacade(unittest.TestCase):
    def test_summary_is_stable(self):
        analysis = TripletAnalysis([3, 1, 4, 1, 5, 9, 2, 6])
        summary = analysis.summary()
        self.assertEqual(summary["length"], 8)
        self.assertEqual(summary["strict"], 16)
        self.assertEqual(summary["non_decreasing"], 20)
        self.assertTrue(summary["has_increasing"])
        self.assertEqual(summary["first"], (0, 2, 4))

    def test_to_list_returns_copy(self):
        analysis = TripletAnalysis([1, 2, 3])
        got = analysis.to_list()
        got.append(99)
        self.assertEqual(analysis.to_list(), [1, 2, 3])

    def test_delegates_match_functions(self):
        analysis = TripletAnalysis([2, 4, 1, 3, 5])
        self.assertEqual(analysis.count_strict(), count_increasing_triplets_naive([2, 4, 1, 3, 5]))
        self.assertEqual(
            analysis.count_non_decreasing(),
            count_non_decreasing_triplets_naive([2, 4, 1, 3, 5]),
        )
        self.assertEqual(analysis.has_increasing(), has_increasing_triplet_naive([2, 4, 1, 3, 5]))
        self.assertEqual(analysis.first_triplet(), first_increasing_triplet_naive([2, 4, 1, 3, 5]))


class TestDeterminism(unittest.TestCase):
    def test_repeated_runs_are_identical(self):
        data = [4, 2, 4, 1, 3, 2]
        first = (
            count_increasing_triplets_naive(data),
            count_non_decreasing_triplets_naive(data),
            has_increasing_triplet_naive(data),
        )
        second = (
            count_increasing_triplets_naive(data),
            count_non_decreasing_triplets_naive(data),
            has_increasing_triplet_naive(data),
        )
        self.assertEqual(first, second)

    def test_input_not_mutated(self):
        data = [3, 1, 2, 4]
        count_increasing_triplets_naive(data)
        first_increasing_triplet_naive(data)
        self.assertEqual(data, [3, 1, 2, 4])


class TestExceptionHierarchy(unittest.TestCase):
    def test_base_class_covers_all(self):
        for exc in (InvalidInputError, InvalidLengthError):
            self.assertTrue(issubclass(exc, TripletError))

    def test_catch_base_class(self):
        with self.assertRaises(TripletError):
            count_increasing_triplets_naive(3)
        with self.assertRaises(TripletError):
            count_increasing_subseq_of_length_naive([1, 2, 3], 0)


if __name__ == "__main__":
    unittest.main()
