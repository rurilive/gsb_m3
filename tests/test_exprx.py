"""exprx 回归测试：覆盖四个已修复缺陷及相关语义。运行：python3 -m unittest discover tests"""

import unittest

from exprx import Evaluator, evaluate


class TestUnaryMinusPower(unittest.TestCase):
    """缺陷 1：一元负号曾绑定得比 ^ 紧，-2^2 被算成 (-2)^2。"""

    def test_negative_power_result(self):
        self.assertEqual(evaluate("-2^2"), -4)

    def test_parenthesized_negative_base(self):
        self.assertEqual(evaluate("(-2)^2"), 4)

    def test_negative_exponent(self):
        self.assertEqual(evaluate("2^-3"), 0.125)

    def test_power_right_assoc(self):
        self.assertEqual(evaluate("2^3^2"), 512)

    def test_double_negation(self):
        self.assertEqual(evaluate("--3"), 3)

    def test_unary_in_arithmetic(self):
        self.assertEqual(evaluate("1 - -2"), 3)
        self.assertEqual(evaluate("3 * -2"), -6)


class TestShortCircuit(unittest.TestCase):
    """缺陷 2：and/or 曾两支都求值，x=0 时右支抛 ZeroDivisionError。"""

    def test_and_short_circuits(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)

    def test_and_evaluates_right_when_left_true(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 1}), True)

    def test_or_short_circuits(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 0}), True)

    def test_or_evaluates_right_when_left_false(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 1}), True)

    def test_unbound_name_not_evaluated(self):
        self.assertIs(evaluate("1 == 1 or missing > 0"), True)
        self.assertIs(evaluate("1 == 0 and missing > 0"), False)

    def test_zero_division_still_raised_when_reached(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("10 / 0")


class TestFloorDivMod(unittest.TestCase):
    """缺陷 3：// 和 % 曾用 int(left/right) 截断，负数结果符号错误。"""

    def test_negative_floor_div(self):
        self.assertEqual(evaluate("-7 // 2"), -4)

    def test_negative_mod(self):
        self.assertEqual(evaluate("-7 % 2"), 1)

    def test_positive_operands(self):
        self.assertEqual(evaluate("7 // 2"), 3)
        self.assertEqual(evaluate("7 % 2"), 1)

    def test_mod_zero_raises(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("7 % 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("7 // 0")


class TestLetScoping(unittest.TestCase):
    """缺陷 4：let 绑定曾写入共享环境且不恢复，污染外层和后续 evaluate。"""

    def test_let_visible_in_body(self):
        self.assertEqual(evaluate("let x = 99 in x + 1"), 100)

    def test_outer_binding_restored(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let x = 99 in x", {"x": 1}), 99)
        self.assertEqual(ev.evaluate("x"), 1)

    def test_let_does_not_leak_across_evaluate(self):
        ev = Evaluator()
        ev.evaluate("let y = 5 in y")
        with self.assertRaises(NameError):
            ev.evaluate("y")

    def test_nested_shadowing(self):
        self.assertEqual(evaluate("let x = 1 in (let x = 99 in x) + x"), 100)

    def test_binding_restored_on_error(self):
        ev = Evaluator()
        with self.assertRaises(ZeroDivisionError):
            ev.evaluate("let x = 99 in 1 / 0", {"x": 1})
        self.assertEqual(ev.evaluate("x"), 1)


class TestGeneralSemantics(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(evaluate("1 + 2 * 3"), 7)
        self.assertEqual(evaluate("2 + 3 > 4 and 1 < 2"), True)

    def test_variables_passed_per_call(self):
        self.assertEqual(evaluate("let rate = 0.9 in amount * rate", {"amount": 80}), 72.0)

    def test_unbound_name_raises(self):
        with self.assertRaises(NameError):
            evaluate("nope")

    def test_comparisons(self):
        self.assertIs(evaluate("1 != 2"), True)
        self.assertIs(evaluate("2 <= 2"), True)


if __name__ == "__main__":
    unittest.main()
