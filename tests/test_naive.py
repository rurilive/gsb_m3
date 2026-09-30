"""assignmatch 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from assignmatch.naive import (
    AssignTools,
    Erro,
    INF,
    MatrixError,
    assignment_cost,
    best_partial_assignment,
    enumerate_permutations,
    is_optimal,
    max_profit_assignment,
    min_cost_assignment,
    permutation_count,
)


# 一张三乘三代价矩阵，最小总代价为五，方案是一号做零号、零号做一号、二号做二号。
SQUARE = [
    [4, 1, 3],
    [2, 0, 5],
    [3, 2, 2],
]

# 二乘三代价矩阵，工人比任务少，最大匹配接两个人。
RECTANGLE = [
    [9, 2, 7],
    [6, 4, 3],
]

# 三乘三矩阵，若干格子不可用（用 None 表示），仍能接满三个人。
BLOCKED = [
    [1, None, 4],
    [None, 2, 8],
    [3, 9, None],
]


class TestMinCostAssignment(unittest.TestCase):
    def test_square_min(self):
        result = min_cost_assignment(SQUARE)
        self.assertEqual(result["cost"], 5)
        self.assertEqual(result["assignment"], [1, 0, 2])

    def test_ties_take_smallest_task(self):
        cost = [[0, 0], [0, 0]]
        result = min_cost_assignment(cost)
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["assignment"], [0, 1])

    def test_negative_costs(self):
        cost = [[-3, -1], [-2, -5]]
        result = min_cost_assignment(cost)
        self.assertEqual(result["cost"], -8)
        self.assertEqual(result["assignment"], [0, 1])

    def test_single_cell(self):
        result = min_cost_assignment([[7]])
        self.assertEqual(result["cost"], 7)
        self.assertEqual(result["assignment"], [0])

    def test_needs_square(self):
        with self.assertRaises(MatrixError):
            min_cost_assignment(RECTANGLE)


class TestMaxProfitAssignment(unittest.TestCase):
    def test_square_max(self):
        result = max_profit_assignment(SQUARE)
        self.assertEqual(result["cost"], 11)
        self.assertEqual(result["assignment"], [0, 2, 1])

    def test_max_differs_from_min(self):
        low = min_cost_assignment(SQUARE)["cost"]
        high = max_profit_assignment(SQUARE)["cost"]
        self.assertNotEqual(low, high)


class TestAssignmentCost(unittest.TestCase):
    def test_total_cost(self):
        self.assertEqual(assignment_cost(SQUARE, [1, 0, 2]), 5)

    def test_length_mismatch(self):
        with self.assertRaises(MatrixError):
            assignment_cost(SQUARE, [0, 1])

    def test_incomplete_rejected(self):
        with self.assertRaises(MatrixError):
            assignment_cost(SQUARE, [0, None, 2])

    def test_out_of_range(self):
        with self.assertRaises(MatrixError):
            assignment_cost(SQUARE, [0, 1, 9])


class TestIsOptimal(unittest.TestCase):
    def test_optimal_for_min(self):
        self.assertTrue(is_optimal(SQUARE, [1, 0, 2], mode="min"))

    def test_not_optimal_for_min(self):
        self.assertFalse(is_optimal(SQUARE, [0, 1, 2], mode="min"))

    def test_optimal_for_max(self):
        self.assertTrue(is_optimal(SQUARE, [0, 2, 1], mode="max"))

    def test_bad_mode(self):
        with self.assertRaises(MatrixError):
            is_optimal(SQUARE, [1, 0, 2], mode="middle")


class TestPartialAssignment(unittest.TestCase):
    def test_rectangle_fills_workers(self):
        result = best_partial_assignment(RECTANGLE)
        self.assertEqual(result["size"], 2)
        self.assertEqual(result["cost"], 5)

    def test_blocked_cells_still_full(self):
        result = best_partial_assignment(BLOCKED)
        self.assertEqual(result["size"], 3)
        self.assertEqual(result["cost"], 9)
        self.assertEqual(result["assignment"], [2, 1, 0])

    def test_infinite_treated_as_blocked(self):
        cost = [[1, INF], [2, 3]]
        result = best_partial_assignment(cost)
        self.assertEqual(result["size"], 2)
        self.assertEqual(result["cost"], 4)


class TestEnumerate(unittest.TestCase):
    def test_permutation_count(self):
        self.assertEqual(permutation_count(0), 1)
        self.assertEqual(permutation_count(3), 6)
        self.assertEqual(permutation_count(5), 120)

    def test_enumerate_order(self):
        self.assertEqual(list(enumerate_permutations(3)), [
            (0, 1, 2),
            (0, 2, 1),
            (1, 0, 2),
            (1, 2, 0),
            (2, 0, 1),
            (2, 1, 0),
        ])


class TestValidation(unittest.TestCase):
    def test_ragged_matrix(self):
        with self.assertRaises(MatrixError):
            min_cost_assignment([[1, 2], [3]])

    def test_empty_matrix(self):
        with self.assertRaises(MatrixError):
            min_cost_assignment([])

    def test_bad_cell(self):
        with self.assertRaises(MatrixError):
            min_cost_assignment([["x", 1], [1, 2]])

    def test_errors_share_base(self):
        with self.assertRaises(Erro):
            min_cost_assignment(RECTANGLE)


class TestAssignTools(unittest.TestCase):
    def test_counts_permutations(self):
        tools = AssignTools(SQUARE)
        tools.reset_permutation_count()
        tools.min_cost_assignment()
        self.assertEqual(tools.permutation_count(), 6)

    def test_counts_accumulate(self):
        tools = AssignTools(SQUARE)
        tools.reset_permutation_count()
        tools.min_cost_assignment()
        tools.max_profit_assignment()
        self.assertEqual(tools.permutation_count(), 12)

    def test_partial_and_cost(self):
        tools = AssignTools(BLOCKED)
        tools.reset_permutation_count()
        result = tools.best_partial_assignment()
        self.assertEqual(result["cost"], 9)
        self.assertGreater(tools.permutation_count(), 0)
        self.assertTrue(tools.is_optimal([2, 1, 0], mode="min"))


if __name__ == "__main__":
    unittest.main()
