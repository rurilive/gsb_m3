"""exprx 防回归测试：优先级表、短路求值、负数取模/整除方向、let 作用域隔离。"""

import unittest

from exprx import Evaluator, evaluate


class TestPrecedence(unittest.TestCase):
    """运算符优先级表（低 → 高）：or < and < 比较 < 加减 < 乘除 < 一元负号 < 乘方。"""

    def test_unary_minus_binds_looser_than_power(self):
        self.assertEqual(evaluate("-2^2"), -4)
        self.assertEqual(evaluate("-(2^2)"), -4)
        self.assertEqual(evaluate("(-2)^2"), 4)

    def test_power_is_right_associative(self):
        self.assertEqual(evaluate("2^3^2"), 512)
        self.assertEqual(evaluate("2^(3^2)"), 512)

    def test_negative_exponent(self):
        self.assertAlmostEqual(evaluate("2^-3"), 0.125)

    def test_power_binds_tighter_than_mul(self):
        self.assertEqual(evaluate("2 * 3 ^ 2"), 18)

    def test_mul_binds_tighter_than_add(self):
        self.assertEqual(evaluate("1 + 2 * 3"), 7)

    def test_add_binds_tighter_than_comparison(self):
        self.assertIs(evaluate("1 + 2 == 3"), True)
        self.assertIs(evaluate("1 + 2 * 2 > 4"), True)

    def test_comparison_binds_tighter_than_and(self):
        self.assertIs(evaluate("1 < 2 and 2 < 3"), True)

    def test_and_binds_tighter_than_or(self):
        self.assertIs(evaluate("1 == 2 and 2 == 2 or 3 == 3"), True)
        self.assertIs(evaluate("1 == 2 and (2 == 2 or 3 == 3)"), False)

    def test_subtraction_is_left_associative(self):
        self.assertEqual(evaluate("10 - 4 - 3"), 3)

    def test_double_negation(self):
        self.assertEqual(evaluate("--3"), 3)


class TestShortCircuit(unittest.TestCase):
    """and/or 短路：左侧已能定值时右侧不求值。"""

    def test_and_skips_right_when_left_false(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)

    def test_and_evaluates_right_when_left_true(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 1}), True)

    def test_or_skips_right_when_left_true(self):
        self.assertIs(evaluate("1 == 1 or 1 / 0 > 0"), True)

    def test_or_evaluates_right_when_left_false(self):
        self.assertIs(evaluate("1 == 2 or 2 == 2"), True)

    def test_and_or_result_is_bool(self):
        self.assertIs(evaluate("1 and 2"), True)
        self.assertIs(evaluate("0 or 2"), True)


class TestFloorDivMod(unittest.TestCase):
    """// 与 % 向下取整（与 Python 一致），余数符号跟随除数。"""

    def test_negative_floor_division(self):
        self.assertEqual(evaluate("-7 // 2"), -4)
        self.assertEqual(evaluate("7 // -2"), -4)
        self.assertEqual(evaluate("-7 // -2"), 3)
        self.assertEqual(evaluate("7 // 2"), 3)

    def test_negative_modulo(self):
        self.assertEqual(evaluate("-7 % 2"), 1)
        self.assertEqual(evaluate("7 % -2"), -1)
        self.assertEqual(evaluate("-7 % -2"), -1)
        self.assertEqual(evaluate("7 % 2"), 1)

    def test_div_mod_identity(self):
        for a, b in [(-7, 2), (7, -2), (-7, -2), (7, 2), (-1, 3)]:
            q = evaluate(f"{a} // {b}")
            r = evaluate(f"{a} % {b}")
            self.assertEqual(q * b + r, a)

    def test_zero_division_still_raises(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 // 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 % 0")


class TestLetScoping(unittest.TestCase):
    """let 绑定只在 body 内可见，不泄漏到外层或后续 evaluate。"""

    def test_let_does_not_leak_to_outer_binding(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let x = 99 in x"), 99)
        self.assertEqual(ev.evaluate("x", {"x": 1}), 1)

    def test_let_does_not_leak_across_evaluate_calls(self):
        ev = Evaluator()
        ev.evaluate("let rate = 0.9 in amount * rate", {"amount": 80})
        with self.assertRaises(NameError):
            ev.evaluate("amount * rate", {"amount": 80})

    def test_inner_let_restores_outer_binding(self):
        self.assertEqual(evaluate("let x = 1 in (let x = 99 in x) + x"), 100)

    def test_let_shadows_variable_argument(self):
        self.assertEqual(evaluate("let x = 2 in x", {"x": 1}), 2)
        self.assertEqual(evaluate("x", {"x": 1}), 1)

    def test_nested_let_body_sees_inner_binding(self):
        self.assertEqual(evaluate("let x = 1 in let x = 2 in x"), 2)


if __name__ == "__main__":
    unittest.main()
