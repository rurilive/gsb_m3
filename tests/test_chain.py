"""chain 现有行为的锁定测试：维度校验、最少乘法次数、最优括号化、方案计数、
括号串转换与合法性判定。

只覆盖当前朴素实现已经给出的结果，后面新增的递推、并列口径与计数另开文件。
"""

import unittest

from chainkit import (
    ChainError,
    check_dims,
    naive_cost,
    naive_count,
    naive_optimal,
    naive_plan_cost,
    parse_plan,
    plan_to_string,
    whole_cost,
    whole_count,
    whole_optimal,
)

CLRS = [30, 35, 15, 5, 10, 20, 25]        # 六个矩阵，教科书例子
THREE = [10, 20, 30, 40]                   # 三个矩阵
UNIFORM4 = [10, 10, 10, 10, 10]            # 四个同维矩阵，并列多
ONE = [10, 20]
EMPTY = [10]                               # 零个矩阵


class TestDims(unittest.TestCase):
    def test_count_is_len_minus_one(self):
        self.assertEqual(check_dims(CLRS), 6)
        self.assertEqual(check_dims(ONE), 1)
        self.assertEqual(check_dims(EMPTY), 0)

    def test_empty_dims_rejected(self):
        with self.assertRaises(ChainError):
            check_dims([])

    def test_zero_dimension_rejected(self):
        with self.assertRaises(ChainError):
            check_dims([10, 0])

    def test_negative_dimension_rejected(self):
        with self.assertRaises(ChainError):
            check_dims([10, -3])

    def test_non_integer_rejected(self):
        with self.assertRaises(ChainError):
            check_dims([10, 2.5])

    def test_bool_rejected(self):
        with self.assertRaises(ChainError):
            check_dims([10, True])

    def test_error_is_chain_error(self):
        self.assertTrue(issubclass(ChainError, Exception))


class TestCost(unittest.TestCase):
    def test_clrs_whole_cost(self):
        self.assertEqual(whole_cost(CLRS), 15125)

    def test_three_matrices_whole_cost(self):
        self.assertEqual(whole_cost(THREE), 18000)

    def test_uniform_four_whole_cost(self):
        self.assertEqual(whole_cost(UNIFORM4), 3000)

    def test_single_matrix_cost_zero(self):
        self.assertEqual(whole_cost(ONE), 0)
        self.assertEqual(naive_cost(ONE, 0, 0), 0)

    def test_empty_chain_cost_zero(self):
        self.assertEqual(whole_cost(EMPTY), 0)

    def test_subrange_cost(self):
        self.assertEqual(naive_cost(CLRS, 0, 1), 30 * 35 * 15)
        self.assertEqual(naive_cost(CLRS, 2, 3), 15 * 5 * 10)

    def test_out_of_range_rejected(self):
        with self.assertRaises(ChainError):
            naive_cost(THREE, 0, 5)

    def test_inverted_range_rejected(self):
        with self.assertRaises(ChainError):
            naive_cost(THREE, 2, 1)


class TestOptimal(unittest.TestCase):
    def test_clrs_optimal_value(self):
        value, _ = whole_optimal(CLRS)
        self.assertEqual(value, 15125)

    def test_clrs_optimal_plan_string(self):
        _, plan = whole_optimal(CLRS)
        self.assertEqual(plan_to_string(CLRS, plan), "((0(12))((34)5))")

    def test_single_matrix_plan_is_leaf(self):
        value, plan = whole_optimal(ONE)
        self.assertEqual(value, 0)
        self.assertEqual(plan, 0)

    def test_empty_chain_plan_is_none(self):
        value, plan = whole_optimal(EMPTY)
        self.assertEqual(value, 0)
        self.assertIsNone(plan)

    def test_optimal_plan_cost_matches_value(self):
        value, plan = whole_optimal(CLRS)
        self.assertEqual(naive_plan_cost(CLRS, plan_to_string(CLRS, plan)), value)


class TestCount(unittest.TestCase):
    def test_clrs_unique(self):
        self.assertEqual(whole_count(CLRS), 1)

    def test_uniform_three_has_two(self):
        self.assertEqual(whole_count([10, 10, 10, 10]), 2)

    def test_uniform_four_has_five(self):
        self.assertEqual(whole_count(UNIFORM4), 5)

    def test_single_matrix_has_one(self):
        self.assertEqual(whole_count(ONE), 1)

    def test_empty_chain_has_one(self):
        self.assertEqual(whole_count(EMPTY), 1)

    def test_count_on_subrange(self):
        self.assertEqual(naive_count([10, 10, 10, 10], 0, 2), 2)


class TestPlan(unittest.TestCase):
    def test_parse_roundtrip(self):
        plan = parse_plan(THREE, "(0(12))")
        self.assertEqual(plan, (0, (1, 2)))

    def test_parse_leaf(self):
        self.assertEqual(parse_plan(ONE, "0"), 0)

    def test_parse_empty_chain(self):
        self.assertIsNone(parse_plan(EMPTY, ""))

    def test_parse_ignores_blank(self):
        self.assertEqual(parse_plan(THREE, " ( 0 ( 1 2 ) ) "), (0, (1, 2)))

    def test_parse_rejects_unbalanced(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0(12)")

    def test_parse_rejects_bad_char(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0(1x))")

    def test_parse_rejects_out_of_range_index(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0(3))")

    def test_parse_rejects_trailing(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(01)2")

    def test_plan_cost_left_grouping(self):
        self.assertEqual(naive_plan_cost(THREE, "((01)2)"), 18000)

    def test_plan_cost_right_grouping(self):
        self.assertEqual(naive_plan_cost(THREE, "(0(12))"), 32000)


class TestPlanParseRejects(unittest.TestCase):
    def test_bare_sequence_rejected(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "01")

    def test_leaf_without_parens_rejected(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0)")

    def test_bad_string_rejected(self):
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0(12)")
        with self.assertRaises(ChainError):
            parse_plan(THREE, "(0(3))")


class TestDeterminism(unittest.TestCase):
    def test_repeat_cost_stable(self):
        self.assertEqual(whole_cost(CLRS), whole_cost(CLRS))

    def test_repeat_optimal_stable(self):
        self.assertEqual(whole_optimal(CLRS), whole_optimal(CLRS))

    def test_repeat_count_stable(self):
        self.assertEqual(whole_count(UNIFORM4), whole_count(UNIFORM4))


if __name__ == "__main__":
    unittest.main()
