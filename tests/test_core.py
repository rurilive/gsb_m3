"""dlx.core 现有行为的锁定测试（基线，一字不改）。

基线把矩阵当成二维表，按行号从小到大枚举、逐列线性检查冲突，规模小的时候
结果正确；这里只锁住在小规模上能稳定复现的现状行为，测试不依赖任何模块级
可变状态。
"""

import unittest

from dlx.core import (
    Erro,
    MatrixError,
    ShapeError,
    column_coverage,
    conflict_columns,
    is_exact_cover,
    minimum_solution,
    search_steps,
    solution_count,
    solve,
    solve_all,
)

# 四行四列样本：第一列只在第零行出现，故第零行必选，只有一个解。
SAMPLE = [
    [1, 0, 1, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 1, 1, 0],
]

# 两列三行样本：整行一行盖满，或者前两行各盖一列，恰有两个解。
TWO = [
    [1, 0],
    [0, 1],
    [1, 1],
]


class TestSolve(unittest.TestCase):
    def test_single_row_single_column(self):
        self.assertEqual(solve([[1]]), [0])

    def test_picks_cover(self):
        self.assertEqual(solve(SAMPLE), [0, 1, 2])

    def test_no_solution(self):
        self.assertEqual(solve([[1, 0], [1, 0]]), [])

    def test_zero_cell_only(self):
        self.assertEqual(solve([[0]]), [])

    def test_empty_matrix(self):
        self.assertEqual(solve([]), [])

    def test_result_is_a_real_cover(self):
        picked = solve(SAMPLE)
        self.assertTrue(is_exact_cover(SAMPLE, picked))


class TestSolveAll(unittest.TestCase):
    def test_two_solutions_sorted(self):
        self.assertEqual(solve_all(TWO), [[0, 1], [2]])

    def test_limit(self):
        self.assertEqual(solve_all(TWO, 1), [[0, 1]])

    def test_limit_zero(self):
        self.assertEqual(solve_all(TWO, 0), [])

    def test_limit_negative(self):
        with self.assertRaises(Erro):
            solve_all(SAMPLE, -1)

    def test_limit_not_int(self):
        with self.assertRaises(Erro):
            solve_all(SAMPLE, 1.5)


class TestMinimumAndCount(unittest.TestCase):
    def test_minimum_short_row_wins(self):
        matrix = [[1, 0], [0, 1], [1, 1]]
        self.assertEqual(minimum_solution(matrix), [2])

    def test_minimum_on_sample(self):
        self.assertEqual(minimum_solution(SAMPLE), [0, 1, 2])

    def test_minimum_none(self):
        self.assertEqual(minimum_solution([[1, 0], [1, 0]]), [])

    def test_count(self):
        self.assertEqual(solution_count(TWO), 2)
        self.assertEqual(solution_count([[1]]), 1)


class TestIsExactCover(unittest.TestCase):
    def test_single_row_classic(self):
        self.assertTrue(is_exact_cover([[1, 1]], [0]))

    def test_good(self):
        self.assertTrue(is_exact_cover(SAMPLE, [0, 1, 2]))

    def test_missing_column(self):
        self.assertFalse(is_exact_cover(SAMPLE, [0, 1]))

    def test_overlap(self):
        self.assertFalse(is_exact_cover(SAMPLE, [1, 3]))

    def test_duplicate_row(self):
        self.assertFalse(is_exact_cover(SAMPLE, [1, 1, 2]))

    def test_empty_matrix_empty_rows(self):
        self.assertTrue(is_exact_cover([], []))

    def test_row_out_of_range(self):
        with self.assertRaises(MatrixError):
            is_exact_cover(SAMPLE, [9])

    def test_row_not_int(self):
        with self.assertRaises(MatrixError):
            is_exact_cover(SAMPLE, ["a"])


class TestHelpers(unittest.TestCase):
    def test_column_coverage(self):
        self.assertEqual(column_coverage(SAMPLE, 0), [0, 2])
        self.assertEqual(column_coverage(SAMPLE, 1), [1])
        self.assertEqual(column_coverage(SAMPLE, 2), [3])

    def test_column_coverage_bad_row(self):
        with self.assertRaises(MatrixError):
            column_coverage(SAMPLE, -1)

    def test_conflict_columns(self):
        self.assertEqual(conflict_columns(SAMPLE, [1, 3]), [1])
        self.assertEqual(conflict_columns(SAMPLE, [0, 1]), [])
        self.assertEqual(conflict_columns(SAMPLE, []), [])

    def test_search_steps_repeatable(self):
        self.assertEqual(search_steps(SAMPLE), search_steps(SAMPLE))


class TestValidation(unittest.TestCase):
    def test_ragged(self):
        with self.assertRaises(ShapeError):
            solve([[1], [1, 0]])

    def test_bad_cell(self):
        with self.assertRaises(MatrixError):
            solve([[1, 2]])

    def test_bad_cell_not_int(self):
        with self.assertRaises(MatrixError):
            solve([[1, "x"]])

    def test_none(self):
        with self.assertRaises(ShapeError):
            solve(None)

    def test_row_not_iterable(self):
        with self.assertRaises(ShapeError):
            solve([1, 2])


if __name__ == "__main__":
    unittest.main()
