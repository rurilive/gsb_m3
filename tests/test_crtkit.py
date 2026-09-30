"""crtkit 现有朴素试值行为的锁定测试。

这些用例把基线的对外行为钉住：逐个候选整数试值的求解、分类判定、
区间枚举、试值步数统计，以及异常层级与几处边界。改造时本文件一个字
都不许改，新行为一律另开测试文件。
"""

import unittest

from crtkit.crtkit import (
    CrtkitError,
    EmptySystemError,
    InvalidBoundsError,
    InvalidModulusError,
    InvalidRangeError,
    NoSolutionError,
    count_in_range,
    count_search_steps,
    has_solution,
    normalize_modulus,
    normalize_residue,
    search_first_solution,
    smallest_non_negative,
    solve,
    solutions_in_range,
)


class TestSearchFirstSolution(unittest.TestCase):
    def test_coprime_pair(self):
        self.assertEqual(search_first_solution([2, 3], [3, 5]), 8)

    def test_three_coprime(self):
        self.assertEqual(search_first_solution([1, 2, 3], [3, 5, 7]), 52)

    def test_non_coprime_pair(self):
        self.assertEqual(search_first_solution([1, 3], [2, 6]), 3)

    def test_reduced_residue(self):
        self.assertEqual(search_first_solution([9], [7]), 2)

    def test_conflict_returns_none(self):
        self.assertIsNone(search_first_solution([0, 1], [2, 4]))

    def test_empty_raises(self):
        with self.assertRaises(EmptySystemError):
            search_first_solution([], [])

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(InvalidModulusError):
            search_first_solution([1, 2], [3])


class TestHasSolution(unittest.TestCase):
    def test_has(self):
        self.assertTrue(has_solution([2, 3], [3, 5]))

    def test_not_has(self):
        self.assertFalse(has_solution([0, 1], [2, 4]))


class TestSolve(unittest.TestCase):
    def test_coprime(self):
        self.assertEqual(solve([2, 3], [3, 5]), 8)

    def test_conflict_raises(self):
        with self.assertRaises(NoSolutionError):
            solve([0, 1], [2, 4])


class TestSmallestNonNegative(unittest.TestCase):
    def test_pair(self):
        self.assertEqual(smallest_non_negative([2, 3], [3, 5]), 8)

    def test_single(self):
        self.assertEqual(smallest_non_negative([3], [10]), 3)


class TestSolutionsInRange(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(solutions_in_range([2, 3], [3, 5], 0, 40), [8, 23, 38])

    def test_negative_low_clamped(self):
        self.assertEqual(solutions_in_range([2, 3], [3, 5], -5, 9), [8])

    def test_count(self):
        self.assertEqual(count_in_range([2, 3], [3, 5], 0, 40), 3)

    def test_reversed_range_raises(self):
        with self.assertRaises(InvalidRangeError):
            solutions_in_range([2, 3], [3, 5], 10, 1)


class TestStepCounting(unittest.TestCase):
    def test_count_matches_first_solution(self):
        self.assertEqual(count_search_steps([2, 3], [3, 5]), 9)

    def test_larger_moduli_cost_more(self):
        self.assertGreater(
            count_search_steps([10, 12], [11, 13]),
            count_search_steps([2, 3], [3, 5]),
        )


class TestNormalizeHelpers(unittest.TestCase):
    def test_normalize_dispatches_residue(self):
        self.assertEqual(normalize_residue(-1, 7), 6)

    def test_normalize_rejects_bad_modulus(self):
        with self.assertRaises(InvalidModulusError):
            normalize_modulus(0)

    def test_all_errors_share_base(self):
        self.assertTrue(issubclass(EmptySystemError, CrtkitError))
        self.assertTrue(issubclass(InvalidBoundsError, CrtkitError))
        self.assertTrue(issubclass(NoSolutionError, CrtkitError))


if __name__ == "__main__":
    unittest.main()
