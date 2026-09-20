"""exprx 防回归测试。

覆盖四类历史缺陷：
1. 运算符优先级表（一元负号 vs 乘方、乘方右结合等）
2. and/or 短路：右支在左侧已定值时不得求值
3. // 与 % 的向下取整方向（含负被除数/负除数）
4. let 绑定的作用域隔离（嵌套遮蔽、求值结束恢复、异常后恢复）
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exprx import Evaluator, evaluate


class OperatorPrecedenceTests(unittest.TestCase):
    """完整优先级表：or < and < 比较 < 加减 < 乘除 < 一元负号 < 乘方。"""

    def test_unary_minus_vs_power(self):
        self.assertEqual(evaluate("-2^2"), -4)
        self.assertEqual(evaluate("-(2)^2"), -4)
        self.assertEqual(evaluate("(-2)^2"), 4)
        self.assertEqual(evaluate("0 - 2^2"), -4)

    def test_unary_minus_vs_multiplication(self):
        self.assertEqual(evaluate("2 * -3"), -6)
        self.assertEqual(evaluate("2 * -3^2"), -18)
        self.assertEqual(evaluate("-6 / 2"), -3)
        self.assertEqual(evaluate("--2"), 2)

    def test_power_right_associative(self):
        self.assertEqual(evaluate("2^3^2"), 512)
        self.assertEqual(evaluate("2^3"), 8)
        self.assertEqual(evaluate("2^-2"), 0.25)

    def test_arithmetic_precedence_table(self):
        self.assertEqual(evaluate("2 + 3 * 4"), 14)
        self.assertEqual(evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(evaluate("10 - 2 - 3"), 5)
        self.assertEqual(evaluate("20 / 4 / 5"), 1)
        self.assertEqual(evaluate("2 + 8 % 3"), 4)

    def test_comparison_and_logical_precedence(self):
        self.assertIs(evaluate("1 < 2 and 3 < 4"), True)
        self.assertIs(evaluate("1 > 2 or 3 < 4"), True)
        self.assertIs(evaluate("1 == 1 and 2 == 2 or 3 == 4"), True)
        self.assertIs(evaluate("1 == 2 or 2 == 2 and 3 == 4"), False)
        self.assertEqual(evaluate("2 + 3 == 5"), True)


class ShortCircuitTests(unittest.TestCase):
    """左支已定值时右支不求值：除零、未绑定变量都不能触发。"""

    def test_and_skips_right_when_false(self):
        ev = Evaluator()
        self.assertIs(ev.evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)
        self.assertIs(evaluate("1 == 2 and undefined_var"), False)
        self.assertIs(evaluate("0 and 1 / 0"), False)

    def test_or_skips_right_when_truthy(self):
        ev = Evaluator()
        self.assertIs(ev.evaluate("x == 0 or 10 / x > 2", {"x": 0}), True)
        self.assertIs(evaluate("1 == 1 or undefined_var"), True)
        self.assertIs(evaluate("1 or 1 / 0"), True)

    def test_short_circuit_returns_plain_bool(self):
        self.assertIsInstance(evaluate("0 or 2"), bool)
        self.assertIs(evaluate("0 or 2"), True)
        self.assertIsInstance(evaluate("1 and 0"), bool)
        self.assertIs(evaluate("1 and 0"), False)

    def test_right_side_still_evaluated_when_needed(self):
        ev = Evaluator()
        self.assertIs(ev.evaluate("x != 0 and 10 / x > 2", {"x": 4}), True)
        self.assertIs(ev.evaluate("x != 0 and 10 / x > 2", {"x": 10}), False)
        self.assertIs(ev.evaluate("x == 1 or x == 2", {"x": 2}), True)


class FloorArithmeticTests(unittest.TestCase):
    """// 向下取整；% 余数与除数同号，且 a == (a // b) * b + a % b。"""

    def test_floor_division_negative_dividend(self):
        self.assertEqual(evaluate("-7 // 2"), -4)
        self.assertEqual(evaluate("-1 // 2"), -1)
        self.assertEqual(evaluate("-8 // 2"), -4)

    def test_floor_division_negative_divisor(self):
        self.assertEqual(evaluate("7 // -2"), -4)
        self.assertEqual(evaluate("-7 // -2"), 3)

    def test_modulo_sign_follows_divisor(self):
        self.assertEqual(evaluate("-7 % 2"), 1)
        self.assertEqual(evaluate("-1 % 2"), 1)
        self.assertEqual(evaluate("7 % -2"), -1)
        self.assertEqual(evaluate("-7 % -2"), -1)
        self.assertEqual(evaluate("7 % 2"), 1)

    def test_floor_identity_all_sign_combinations(self):
        for a in (-7, -6, -1, 0, 1, 6, 7):
            for b in (-3, -2, 2, 3):
                q = evaluate(f"{a} // {b}")
                r = evaluate(f"{a} % {b}")
                self.assertEqual(q * b + r, a, f"{a} // {b}, {a} % {b}")

    def test_division_by_zero_still_raises(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 % 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 // 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 / 0")


class LetScopeTests(unittest.TestCase):
    """let 绑定仅在 body 可见，退出后外层同名绑定恢复，不跨 evaluate 泄漏。"""

    def test_binding_visible_only_in_body(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let scoped_only = 99 in scoped_only"), 99)
        with self.assertRaises(NameError):
            ev.evaluate("scoped_only")

    def test_nested_shadowing_restores_outer(self):
        self.assertEqual(
            evaluate("let x = 1 in (let x = 99 in x) + x"),
            100,
        )
        self.assertEqual(evaluate("let x = 5 in let x = 6 in x"), 6)

    def test_outer_binding_not_mutated(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let x = 99 in x", {"x": 1}), 99)
        self.assertEqual(ev.evaluate("x"), 1)

    def test_no_leak_between_evaluate_calls(self):
        ev = Evaluator()
        ev.evaluate("let rate = 0.9 in 80 * rate")
        with self.assertRaises(NameError):
            ev.evaluate("rate")

    def test_binding_restored_when_body_raises(self):
        ev = Evaluator()
        with self.assertRaises(ZeroDivisionError):
            ev.evaluate("let z = 1 in 1 / 0")
        with self.assertRaises(NameError):
            ev.evaluate("z")

    def test_let_value_can_use_outer_bindings(self):
        ev = Evaluator()
        self.assertEqual(
            ev.evaluate("let y = x + 1 in y * 2", {"x": 10}),
            22,
        )


if __name__ == "__main__":
    unittest.main()
