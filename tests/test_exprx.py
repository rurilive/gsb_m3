"""exprx 防回归测试：覆盖一元负号、短路求值、地板除/取模、let 作用域。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exprx import Evaluator, evaluate


class UnaryMinusPowerTests(unittest.TestCase):
    def test_negative_base_square(self):
        self.assertEqual(evaluate("-2^2"), -4)

    def test_negative_base_odd_power(self):
        self.assertEqual(evaluate("-2^3"), -8)

    def test_power_right_associative(self):
        self.assertEqual(evaluate("2^3^2"), 512)

    def test_double_negative(self):
        self.assertEqual(evaluate("--2^2"), 4)
        self.assertEqual(evaluate("-(-2)^2"), -4)

    def test_negative_exponent(self):
        self.assertAlmostEqual(evaluate("2^-2"), 0.25)
        self.assertAlmostEqual(evaluate("2^-3"), 0.125)

    def test_unary_minus_with_mul_div(self):
        self.assertEqual(evaluate("2 * -3"), -6)
        self.assertEqual(evaluate("-6 / 2"), -3)


class ShortCircuitTests(unittest.TestCase):
    def test_and_short_circuits_on_false(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)

    def test_or_short_circuits_on_true(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 0}), True)

    def test_and_evaluates_right_when_left_true(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 4}), True)
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 10}), False)

    def test_or_evaluates_right_when_left_false(self):
        self.assertIs(evaluate("x != 0 or 10 / x > 2", {"x": 4}), True)

    def test_chained_short_circuit(self):
        self.assertIs(evaluate("1 == 0 and 1 / 0 > 0 or 2 == 2"), True)
        self.assertIs(evaluate("1 == 1 or 1 / 0 > 0 and 2 == 3"), True)

    def test_results_are_bool(self):
        self.assertIsInstance(evaluate("1 and 2"), bool)
        self.assertIsInstance(evaluate("0 or 3"), bool)


class FloorDivModuloTests(unittest.TestCase):
    def test_negative_modulo(self):
        self.assertEqual(evaluate("-7 % 2"), 1)
        self.assertEqual(evaluate("7 % -2"), -1)
        self.assertEqual(evaluate("-7 % -2"), -1)

    def test_positive_modulo(self):
        self.assertEqual(evaluate("7 % 2"), 1)

    def test_negative_floor_div(self):
        self.assertEqual(evaluate("-7 // 2"), -4)
        self.assertEqual(evaluate("7 // -2"), -4)
        self.assertEqual(evaluate("-7 // -2"), 3)

    def test_positive_floor_div(self):
        self.assertEqual(evaluate("7 // 2"), 3)

    def test_floor_div_keeps_integer_type(self):
        self.assertIsInstance(evaluate("7 // 2"), int)
        self.assertIsInstance(evaluate("-7 // 2"), int)


class LetScopeTests(unittest.TestCase):
    def test_binding_visible_only_in_body(self):
        self.assertEqual(evaluate("let x = 99 in x + 1"), 100)
        with self.assertRaises(NameError):
            evaluate("x")

    def test_outer_binding_restored(self):
        ev = Evaluator()
        ev.evaluate("let x = 1 in x")
        ev.evaluate("let x = 99 in let x = 5 in x")
        with self.assertRaises(NameError):
            ev.evaluate("x")

    def test_nested_let_restores_outer_same_name(self):
        self.assertEqual(evaluate("let x = 1 in (let x = 99 in x) + x"), 100)

    def test_let_does_not_shadow_caller_binding(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let x = 99 in x", {"x": 1}), 99)
        self.assertEqual(ev.evaluate("x"), 1)

    def test_no_leakage_across_rules(self):
        ev = Evaluator()
        ev.evaluate("let x = 99 in x")
        self.assertEqual(ev.evaluate("let y = x + 1 in y", {"x": 10}), 11)


if __name__ == "__main__":
    unittest.main()
