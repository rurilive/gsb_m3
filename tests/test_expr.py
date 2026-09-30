"""evalx 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from evalx.expr import (
    ExprError,
    InvalidSyntaxError,
    UnbalancedParenError,
    DivisionByZeroError,
    UnknownVariableError,
    EmptyExpressionError,
    Expression,
)


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_atom(self):
        self.assertEqual(self.ev.evaluate("7"), 7)

    def test_precedence(self):
        self.assertEqual(self.ev.evaluate("1+2*3"), 7)

    def test_left_assoc_same_level(self):
        self.assertEqual(self.ev.evaluate("2-3-4"), -5)

    def test_parentheses(self):
        self.assertEqual(self.ev.evaluate("(1+2)*3"), 9)

    def test_nested_parentheses(self):
        self.assertEqual(self.ev.evaluate("((1+2))*((3+4))"), 21)

    def test_unary_minus(self):
        self.assertEqual(self.ev.evaluate("-5+10"), 5)

    def test_double_unary_minus(self):
        self.assertEqual(self.ev.evaluate("--5"), 5)

    def test_unary_before_paren(self):
        self.assertEqual(self.ev.evaluate("-(3+4)"), -7)

    def test_unary_after_operator(self):
        self.assertEqual(self.ev.evaluate("2*-3"), -6)

    def test_unary_inside_paren(self):
        self.assertEqual(self.ev.evaluate("(-5)"), -5)

    def test_whitespace_ignored(self):
        self.assertEqual(self.ev.evaluate("  1 +  2 * 3 "), 7)

    def test_integer_floor_division(self):
        self.assertEqual(self.ev.evaluate("10/3"), 3)
        self.assertEqual(self.ev.evaluate("-10/3"), -4)

    def test_variables(self):
        vars_ = {"a": 2, "b": 5, "c": 1}
        self.assertEqual(self.ev.evaluate("a*b+c", vars_), 11)

    def test_variable_all_constant(self):
        vars_ = {"a": 3, "b": 3}
        self.assertEqual(self.ev.evaluate("a+b", vars_), 6)


class TestToRpn(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_plain(self):
        self.assertEqual(self.ev.to_rpn("1+2"), [1, 2, "+"])

    def test_precedence(self):
        self.assertEqual(self.ev.to_rpn("1+2*3"), [1, 2, 3, "*", "+"])

    def test_parentheses(self):
        self.assertEqual(self.ev.to_rpn("(1+2)*3"), [1, 2, "+", 3, "*"])

    def test_unary(self):
        self.assertEqual(self.ev.to_rpn("-5+10"), ["u", 5, 10, "+"])

    def test_left_assoc(self):
        self.assertEqual(self.ev.to_rpn("2-3-4"), [2, 3, "-", 4, "-"])

    def test_unary_after_operator(self):
        self.assertEqual(self.ev.to_rpn("2*-3"), [2, "u", 3, "*"])


class TestBatch(unittest.TestCase):
    def test_results_and_argmax(self):
        ev = Expression()
        results, best = ev.batch_evaluate(["1+1", "3*3", "10-4"], {})
        self.assertEqual(results, [2, 9, 6])
        self.assertEqual(best, 1)

    def test_with_variables(self):
        ev = Expression()
        results, best = ev.batch_evaluate(["a+1", "a*2"], {"a": 4})
        self.assertEqual(results, [5, 8])
        self.assertEqual(best, 1)

    def test_empty_batch(self):
        ev = Expression()
        with self.assertRaises(EmptyExpressionError):
            ev.batch_evaluate([], {})


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_empty(self):
        with self.assertRaises(EmptyExpressionError):
            self.ev.evaluate("")
        with self.assertRaises(EmptyExpressionError):
            self.ev.evaluate("   ")

    def test_unbalanced_left(self):
        with self.assertRaises(UnbalancedParenError):
            self.ev.evaluate("(1+2")

    def test_unbalanced_right(self):
        with self.assertRaises(UnbalancedParenError):
            self.ev.evaluate("1+2)")

    def test_division_by_zero(self):
        with self.assertRaises(DivisionByZeroError):
            self.ev.evaluate("1/0")

    def test_unknown_variable(self):
        with self.assertRaises(UnknownVariableError):
            self.ev.evaluate("x+1", {})

    def test_invalid_operator_position(self):
        with self.assertRaises(InvalidSyntaxError):
            self.ev.evaluate("1+*2")

    def test_leading_operator(self):
        with self.assertRaises(InvalidSyntaxError):
            self.ev.evaluate("*1")

    def test_trailing_operator(self):
        with self.assertRaises(InvalidSyntaxError):
            self.ev.evaluate("1+")

    def test_empty_paren(self):
        with self.assertRaises(InvalidSyntaxError):
            self.ev.evaluate("()")

    def test_all_errors_share_base(self):
        for bad in ["", "(1+2", "1/0", "x", "1+*2"]:
            with self.assertRaises(ExprError):
                self.ev.evaluate(bad)


class TestScanCount(unittest.TestCase):
    def test_reset_per_call(self):
        ev = Expression()
        ev.evaluate("1+2*3")
        first = ev.scan_count()
        ev.evaluate("1+2*3")
        self.assertEqual(ev.scan_count(), first)

    def test_deeper_paren_scans_more(self):
        ev = Expression()
        ev.evaluate("7")
        shallow = ev.scan_count()
        ev.evaluate("(((((((7)))))))")
        self.assertGreater(ev.scan_count(), shallow)

    def test_determinism(self):
        ev = Expression()
        a = [ev.evaluate("1+2*3"), ev.to_rpn("(1+2)*3")]
        b = [ev.evaluate("1+2*3"), ev.to_rpn("(1+2)*3")]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
