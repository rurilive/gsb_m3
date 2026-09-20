"""regex 操作符与 not() 组合器的行为测试。"""

import unittest

from flagr import RuleCompileError, compile_rules


def compile_one(rule_line):
    return compile_rules(f"flag t\n{rule_line}\ndefault off\n")


class TestRegexMatching(unittest.TestCase):
    def test_search_semantics_not_fullmatch(self):
        engine = compile_one('when email regex "@corp\\.example\\.com$" -> on\n')
        self.assertTrue(
            engine.evaluate("t", {"email": "a@corp.example.com"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "a@corp.example.com.evil.cn"}).enabled)

    def test_substring_search(self):
        engine = compile_one('when path regex "^/api/v\\d+/" -> on\n')
        self.assertTrue(engine.evaluate("t", {"path": "/api/v2/users"}).enabled)
        self.assertFalse(engine.evaluate("t", {"path": "/web/v2/users"}).enabled)

    def test_missing_field_is_miss(self):
        engine = compile_one('when email regex "a" -> on\n')
        self.assertFalse(engine.evaluate("t", {}).enabled)

    def test_non_string_ctx_is_miss(self):
        engine = compile_one('when x regex "1" -> on\n')
        self.assertFalse(engine.evaluate("t", {"x": 123}).enabled)
        self.assertFalse(engine.evaluate("t", {"x": True}).enabled)
        self.assertFalse(engine.evaluate("t", {"x": None}).enabled)

    def test_describe(self):
        engine = compile_one('when email regex "@corp\\.com$" -> on\n')
        self.assertEqual(
            engine.spec("t").rules[0].matcher.describe(),
            r'email regex "@corp\.com$"')

    def test_regex_inside_combinators(self):
        engine = compile_one(
            'when and(email regex "@corp\\.com$", age ge 18) -> on\n')
        self.assertTrue(engine.evaluate(
            "t", {"email": "a@corp.com", "age": 20}).enabled)
        self.assertFalse(engine.evaluate(
            "t", {"email": "a@corp.com", "age": 9}).enabled)

    def test_explain_golden(self):
        d = compile_one('when email regex "@corp\\.com$" -> on\n').evaluate(
            "t", {"email": "a@corp.com"})
        self.assertEqual(
            d.explain(),
            "t -> on (rule#1)\n"
            r'  #1 email regex "@corp\.com$" hit')


class TestNotCombinator(unittest.TestCase):
    def test_basic_negation(self):
        engine = compile_one("when not(plan eq pro) -> on\n")
        self.assertTrue(engine.evaluate("t", {"plan": "free"}).enabled)
        self.assertFalse(engine.evaluate("t", {"plan": "pro"}).enabled)

    def test_not_of_miss_is_hit(self):
        # 子条件因字段缺失判 miss，取反后为 hit
        engine = compile_one("when not(vip eq true) -> on\n")
        self.assertTrue(engine.evaluate("t", {}).enabled)

    def test_not_of_combinator(self):
        engine = compile_one("when not(and(country eq CN, age ge 18)) -> on\n")
        self.assertFalse(
            engine.evaluate("t", {"country": "CN", "age": 20}).enabled)
        self.assertTrue(
            engine.evaluate("t", {"country": "CN", "age": 9}).enabled)

    def test_nested_not(self):
        engine = compile_one("when not(not(plan eq pro)) -> on\n")
        self.assertTrue(engine.evaluate("t", {"plan": "pro"}).enabled)
        self.assertFalse(engine.evaluate("t", {"plan": "free"}).enabled)

    def test_deep_nesting_with_and_or(self):
        engine = compile_one(
            "when or(not(env eq prod), and(not(plan eq pro), age lt 18)) -> on\n")
        self.assertTrue(engine.evaluate("t", {"env": "staging"}).enabled)
        self.assertTrue(engine.evaluate(
            "t", {"env": "prod", "plan": "free", "age": 9}).enabled)
        self.assertFalse(engine.evaluate(
            "t", {"env": "prod", "plan": "pro", "age": 9}).enabled)

    def test_not_with_regex(self):
        engine = compile_one('when not(email regex "@corp\\.com$") -> on\n')
        self.assertTrue(engine.evaluate("t", {"email": "a@gmail.com"}).enabled)
        self.assertFalse(engine.evaluate("t", {"email": "a@corp.com"}).enabled)

    def test_describe(self):
        engine = compile_one("when not(and(a eq 1, b eq 2)) -> on\n")
        self.assertEqual(
            engine.spec("t").rules[0].matcher.describe(),
            "not(and(a eq 1, b eq 2))")


class TestCompileErrors(unittest.TestCase):
    def assert_error(self, text, line, col, message):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(text)
        self.assertEqual(cm.exception.line, line)
        self.assertEqual(cm.exception.col, col)
        self.assertEqual(str(cm.exception), f"{line}:{col}: {message}")

    def test_not_rejects_two_args(self):
        self.assert_error(
            "flag a\nwhen not(x eq 1, y eq 2) -> on\n",
            2, 6, "not 只接受 1 个参数")

    def test_and_or_arity_unchanged(self):
        self.assert_error(
            "flag a\nwhen and(x eq 1) -> on\n",
            2, 6, "and 至少需要 2 个参数")

    def test_regex_value_must_be_string(self):
        self.assert_error(
            "flag a\nwhen email regex 123 -> on\n",
            2, 18, "regex 需要带引号的正则模式，得到 '123'")

    def test_invalid_regex(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules('flag a\nwhen email regex "(a" -> on\n')
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 18))
        self.assertTrue(cm.exception.message.startswith("非法正则"))

    def test_nested_quantifiers_rejected(self):
        dangerous = [
            "(a+)+", "(a*)*", r"(\d+)+$", "(a+){2,}", "((a+)+)b",
            "(a|b+)*", r"(a+)+@(x\.)*", r"^\w+([-+.]\w+)*@",
        ]
        for pattern in dangerous:
            with self.subTest(pattern=pattern):
                with self.assertRaises(RuleCompileError) as cm:
                    compile_rules(f'flag a\nwhen email regex "{pattern}" -> on\n')
                self.assertIn("嵌套量词", cm.exception.message)
                self.assertEqual((cm.exception.line, cm.exception.col), (2, 18))

    def test_safe_patterns_accepted(self):
        safe = [
            "a+", "(abc)+", "(a|b)+", "[a-z]+", "(a+)?", "(a+){2}",
            "(a+){2,5}", r"@corp\.example\.com$", "(?:ab|cd)+",
            r"x{3}y{2,}",
        ]
        for pattern in safe:
            with self.subTest(pattern=pattern):
                engine = compile_one(f'when email regex "{pattern}" -> on\n')
                self.assertIn("t", engine.flags)


if __name__ == "__main__":
    unittest.main()
