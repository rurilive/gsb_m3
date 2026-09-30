"""基线测试：锁住改造前 slopeopt.core 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - optimize 对每个下标枚举全部更早的下标，逐个算代价再取最小；
  - 决策下标并列时取更小的下标；
  - dp[0] 取第一个权值本身；
  - 各步比较次数与候选转移总数如实报出；
  - 非法输入在进入求解前快速失败，异常统一继承 OptErro。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slopeopt.core import (  # noqa: E402
    OptErro,
    OptKit,
    Program,
    ProgramErro,
    SequenceErro,
)


SINGLE = [4]
PAIR = [3, 4]
MAIN = [4, -3, 7, 2, -5]
STEP2 = [10, 6, 1, 8, 3, 5]
HUGE = 10 ** 30


class TestOptimizeBaseline(unittest.TestCase):
    def test_single_element_dp_is_value_itself(self):
        res = OptKit(Program(slope=3, intercept=5, k=1)).optimize(SINGLE)
        self.assertEqual(res["dp"], [4])
        self.assertEqual(res["best"], [0])
        self.assertEqual(res["steps"], 0)

    def test_main_case_dp_and_decisions(self):
        res = OptKit(Program(slope=3, intercept=5, k=1)).optimize(MAIN)
        self.assertEqual(res["dp"], [4, 10, 11, 12, 13])
        self.assertEqual(res["best"], [0, 0, 0, 0, 0])

    def test_ties_take_smallest_index(self):
        res = OptKit(Program(slope=0, intercept=7, k=1)).optimize([5, 0, 5, 10])
        self.assertEqual(res["dp"], [5, 13, 14, 15])
        self.assertEqual(res["best"], [0, 0, 0, 0])

    def test_negative_slope_step_two(self):
        res = OptKit(Program(slope=-2, intercept=4, k=2)).optimize(STEP2)
        self.assertEqual(res["dp"], [10, 6, 18, 12, 14, 14])
        self.assertEqual(res["best"], [0, 1, 0, 1, 1, 3])

    def test_too_short_for_step_two_copies_weights(self):
        res = OptKit(Program(slope=5, intercept=1, k=2)).optimize(PAIR)
        self.assertEqual(res["dp"], [3, 4])
        self.assertEqual(res["best"], [0, 1])

    def test_steps_counted_per_candidate(self):
        res = OptKit(Program(slope=3, intercept=5, k=1)).optimize(PAIR)
        self.assertEqual(res["steps"], 1)

    def test_steps_zero_when_no_transition_possible(self):
        res = OptKit(Program(slope=1, intercept=0, k=9)).optimize(MAIN)
        self.assertEqual(res["steps"], 0)
        self.assertEqual(res["dp"], list(MAIN))

    def test_big_integer_costs_do_not_overflow(self):
        res = OptKit(Program(slope=0, intercept=HUGE, k=1)).optimize([1, 2, 3, 4])
        self.assertEqual(res["dp"], [1, HUGE + 2, HUGE + 3, HUGE + 4])

    def test_trailing_sum_never_wins(self):
        res = OptKit(Program(slope=0, intercept=100, k=1)).optimize([1, 2, 3, 4])
        self.assertEqual(res["best"], [0, 0, 0, 0])


class TestValidationBaseline(unittest.TestCase):
    def test_empty_weights_raise(self):
        with self.assertRaises(SequenceErro):
            OptKit(Program(slope=1, intercept=0, k=1)).optimize([])

    def test_empty_weights_is_opt_erro(self):
        with self.assertRaises(OptErro):
            OptKit(Program(slope=1, intercept=0, k=1)).optimize([])

    def test_non_integer_weight_raises(self):
        with self.assertRaises(SequenceErro):
            OptKit(Program(slope=1, intercept=0, k=1)).optimize([1, 2.5, 3])

    def test_bool_weight_rejected(self):
        with self.assertRaises(SequenceErro):
            OptKit(Program(slope=1, intercept=0, k=1)).optimize([1, True])

    def test_non_integer_slope_raises(self):
        with self.assertRaises(ProgramErro):
            Program(slope=1.5, intercept=0, k=1)

    def test_zero_step_raises(self):
        with self.assertRaises(ProgramErro):
            Program(slope=1, intercept=0, k=0)

    def test_negative_step_raises(self):
        with self.assertRaises(ProgramErro):
            Program(slope=1, intercept=0, k=-3)

    def test_program_must_be_program_instance(self):
        with self.assertRaises(ProgramErro):
            OptKit("not a program")

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SequenceErro, OptErro))
        self.assertTrue(issubclass(ProgramErro, OptErro))
        self.assertTrue(issubclass(OptErro, Exception))


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        k1 = OptKit(Program(slope=3, intercept=5, k=1))
        k2 = OptKit(Program(slope=3, intercept=5, k=1))
        self.assertEqual(k1.optimize(MAIN), k2.optimize(MAIN))

    def test_counts_reset_between_calls(self):
        kit = OptKit(Program(slope=3, intercept=5, k=1))
        kit.optimize(MAIN)
        first = kit.steps
        kit.optimize(MAIN)
        self.assertEqual(kit.steps, first)


class TestCompareBaseline(unittest.TestCase):
    def test_compare_agrees_by_construction(self):
        res = OptKit(Program(slope=3, intercept=5, k=1)).compare(MAIN)
        self.assertTrue(res["agree"])
        self.assertEqual(res["baseline"]["dp"], res["fast"]["dp"])
        self.assertEqual(res["baseline"]["best"], res["fast"]["best"])
        self.assertEqual(res["baseline_steps"], res["fast_steps"])

    def test_compare_echoes_weights(self):
        res = OptKit(Program(slope=3, intercept=5, k=1)).compare(MAIN)
        self.assertEqual(res["weights"], list(MAIN))


if __name__ == "__main__":
    unittest.main()
