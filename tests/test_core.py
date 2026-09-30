"""基线测试：锁住改造前 dncopt.core.Optimizer 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - seg_sum 对指定段逐项累加求和，seg_cost 取该段和的平方；
  - segmented_dp / decision_points 对每一组、每个前缀枚举全部上一刀位置，
    取总代价最小的那一刀，并列时取下标最小者；
  - min_cost 取整条序列分成指定组数的最小总代价；
  - 计数 naive_op_visits 记录最近一次调用里枚举切割点的次数，调用前归零。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dncopt.core import (  # noqa: E402
    DncoptErro,
    InputErro,
    Optimizer,
)


CHAIN = [1, 2, 3, 4, 5]


class TestConstructionBaseline(unittest.TestCase):
    def test_costs_kept_in_order(self):
        self.assertEqual(Optimizer(CHAIN).costs, tuple(CHAIN))

    def test_zero_costs_allowed(self):
        self.assertEqual(Optimizer([0, 0, 0]).costs, (0, 0, 0))

    def test_empty_allowed(self):
        self.assertEqual(Optimizer([]).costs, ())

    def test_can_pass_iterator(self):
        self.assertEqual(Optimizer(iter([2, 5])).costs, (2, 5))

    def test_size(self):
        self.assertEqual(Optimizer(CHAIN).size, 5)

    def test_none_costs_raises(self):
        with self.assertRaises(InputErro):
            Optimizer(None)

    def test_bool_cost_raises(self):
        with self.assertRaises(InputErro):
            Optimizer([1, True, 3])

    def test_float_cost_raises(self):
        with self.assertRaises(InputErro):
            Optimizer([1, 2.5, 3])

    def test_negative_cost_raises(self):
        with self.assertRaises(InputErro):
            Optimizer([1, -2, 3])


class TestSegmentBaseline(unittest.TestCase):
    def setUp(self):
        self.opt = Optimizer(CHAIN)

    def test_sum_single_element(self):
        self.assertEqual(self.opt.seg_sum(2, 2), 2)

    def test_sum_full_span(self):
        self.assertEqual(self.opt.seg_sum(1, 5), 15)

    def test_sum_middle_span(self):
        self.assertEqual(self.opt.seg_sum(2, 4), 9)

    def test_cost_is_sum_squared(self):
        self.assertEqual(self.opt.seg_cost(2, 4), 81)

    def test_cost_single_element(self):
        self.assertEqual(self.opt.seg_cost(3, 3), 9)

    def test_left_out_of_range_raises(self):
        with self.assertRaises(InputErro):
            self.opt.seg_sum(0, 2)

    def test_right_out_of_range_raises(self):
        with self.assertRaises(InputErro):
            self.opt.seg_sum(1, 6)

    def test_reversed_span_raises(self):
        with self.assertRaises(InputErro):
            self.opt.seg_sum(4, 2)

    def test_bool_index_raises(self):
        with self.assertRaises(InputErro):
            self.opt.seg_sum(True, 2)


class TestSegmentedBaseline(unittest.TestCase):
    def test_chain_one_group(self):
        self.assertEqual(Optimizer(CHAIN).min_cost(1), 225)

    def test_chain_two_groups(self):
        self.assertEqual(Optimizer(CHAIN).min_cost(2), 117)

    def test_chain_three_groups(self):
        self.assertEqual(Optimizer(CHAIN).min_cost(3), 77)

    def test_chain_five_groups_are_singletons(self):
        # 五组即每个元素自成一段，代价为各元素平方之和。
        self.assertEqual(Optimizer(CHAIN).min_cost(5), 55)

    def test_classic_four_two_groups(self):
        self.assertEqual(Optimizer([4, 1, 1, 4]).min_cost(2), 50)

    def test_classic_four_three_groups(self):
        self.assertEqual(Optimizer([4, 1, 1, 4]).min_cost(3), 36)

    def test_zero_sequence_two_groups(self):
        self.assertEqual(Optimizer([0, 0, 0]).min_cost(2), 0)

    def test_more_groups_than_elements_raises(self):
        with self.assertRaises(InputErro):
            Optimizer(CHAIN).min_cost(6)

    def test_negative_groups_raises(self):
        with self.assertRaises(InputErro):
            Optimizer(CHAIN).min_cost(-1)

    def test_bool_groups_raises(self):
        with self.assertRaises(InputErro):
            Optimizer(CHAIN).min_cost(True)

    def test_empty_zero_groups_is_zero(self):
        self.assertEqual(Optimizer([]).min_cost(0), 0)

    def test_empty_one_group_raises(self):
        with self.assertRaises(InputErro):
            Optimizer([]).min_cost(1)

    def test_segmented_dp_shape(self):
        dp = Optimizer(CHAIN).segmented_dp(2)
        self.assertEqual(len(dp), 3)
        self.assertEqual(len(dp[0]), 6)
        self.assertEqual(dp[0][0], 0)
        self.assertIsNone(dp[0][1])

    def test_segmented_dp_first_group_row(self):
        dp = Optimizer(CHAIN).segmented_dp(2)
        self.assertEqual(tuple(dp[1]), (None, 1, 9, 36, 100, 225))

    def test_segmented_dp_second_group_row(self):
        dp = Optimizer(CHAIN).segmented_dp(2)
        self.assertEqual(tuple(dp[2]), (None, None, 5, 18, 52, 117))

    def test_segmented_dp_unreachable_is_none(self):
        dp = Optimizer(CHAIN).segmented_dp(4)
        self.assertIsNone(dp[4][3])
        self.assertIsNotNone(dp[4][4])


class TestDecisionBaseline(unittest.TestCase):
    def test_chain_two_groups_decision(self):
        # 前 3 个一段、余下两个一段，代价 36 加 81 得 117，为两组划分的最小。
        self.assertEqual(Optimizer(CHAIN).decision_points(2)[2][5], 3)

    def test_classic_four_two_groups(self):
        self.assertEqual(Optimizer([4, 1, 1, 4]).decision_points(2)[2][4], 2)

    def test_classic_four_four_groups(self):
        self.assertEqual(Optimizer([4, 1, 1, 4]).decision_points(4)[4][4], 3)

    def test_decision_table_shape(self):
        dec = Optimizer(CHAIN).decision_points(2)
        self.assertEqual(len(dec), 3)
        self.assertEqual(len(dec[0]), 6)
        self.assertIsNone(dec[0][1])

    def test_first_group_row_decision_is_zero(self):
        dec = Optimizer(CHAIN).decision_points(2)
        self.assertEqual(tuple(dec[1]), (None, 0, 0, 0, 0, 0))

    def test_tie_takes_smallest_index(self):
        # 序列 [1, 1, 1] 分成两组，第一刀在第一或第二处总代价都是 5，取更小的下标。
        self.assertEqual(Optimizer([1, 1, 1]).decision_points(2)[2][3], 1)

    def test_tie_three_way_takes_smallest(self):
        # 序列 [0, 0, 0, 1] 分成两组，三处切割的总代价同为 1，取下标最小者。
        self.assertEqual(Optimizer([0, 0, 0, 1]).decision_points(2)[2][4], 1)


class TestScaleBaseline(unittest.TestCase):
    def test_naive_visit_counter_positive(self):
        opt = Optimizer(CHAIN)
        opt.segmented_dp(2)
        self.assertGreater(opt.naive_op_visits, 0)

    def test_naive_visit_counter_grows_with_length(self):
        # 长度为五、分成两组时，逐层枚举上一刀位置的次数为 十五 加 十，合计二十五。
        opt = Optimizer(CHAIN)
        opt.segmented_dp(2)
        self.assertEqual(opt.naive_op_visits, 25)

    def test_counter_reset_per_call(self):
        opt = Optimizer(CHAIN)
        opt.segmented_dp(2)
        first = opt.naive_op_visits
        opt.segmented_dp(2)
        self.assertEqual(opt.naive_op_visits, first)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = Optimizer(CHAIN)
        b = Optimizer(CHAIN)
        self.assertEqual(a.min_cost(3), b.min_cost(3))
        self.assertEqual(a.decision_points(3), b.decision_points(3))

    def test_no_shared_state_across_instances(self):
        a = Optimizer([1, 1])
        b = Optimizer([9, 9, 9])
        self.assertNotEqual(a.costs, b.costs)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(InputErro, DncoptErro))
        self.assertTrue(issubclass(DncoptErro, Exception))


if __name__ == "__main__":
    unittest.main()
