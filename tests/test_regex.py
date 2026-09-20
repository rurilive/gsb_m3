"""regex 操作符与 not() 组合器的行为测试。"""

import threading
import unittest

from flagr import (
    Matcher,
    Not,
    Regex,
    RegexSafetyError,
    RuleCompileError,
    compile_rules,
)


def compile_one(rule_line):
    return compile_rules(f"flag t\n{rule_line}\ndefault off\n")


class TestRegexSemantics(unittest.TestCase):
    def test_search_semantics_not_fullmatch(self):
        engine = compile_one(r'when email regex "corp" -> on' + "\n")
        self.assertTrue(
            engine.evaluate("t", {"email": "alice@corp.example.com"}).enabled)

    def test_domain_anchor(self):
        engine = compile_one(r'when email regex "@corp\.example\.com$" -> on'
                             + "\n")
        self.assertTrue(
            engine.evaluate("t", {"email": "a@corp.example.com"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "a@corp.example.com.cn"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "a@example.com"}).enabled)

    def test_missing_field_is_miss(self):
        engine = compile_one(r'when email regex "x" -> on' + "\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)

    def test_non_string_context_coerced(self):
        engine = compile_one(r'when n regex "^1" -> on' + "\n")
        self.assertTrue(engine.evaluate("t", {"n": 1024}).enabled)
        self.assertFalse(engine.evaluate("t", {"n": 2048}).enabled)

    def test_pattern_precompiled_and_immutable(self):
        matcher = Regex("email", r"@corp\.example\.com$")
        self.assertIsInstance(matcher, Matcher)
        import re
        self.assertEqual(matcher.regex.search("a@corp.example.com").group(),
                         "@corp.example.com")
        self.assertEqual(matcher.describe(),
                         'email regex "@corp\\.example\\.com$"')


class TestRegexFailuresAtCompileTime(unittest.TestCase):
    DANGEROUS = [
        r"(a+)+",
        r"([0-9]+)*",
        r"(\s*)*",
        r"(a?){10,}",
        r"(a|aa)+",
        r"(a|a)*",
        r"x(a+)+y",
        r"(?:\w+|\d+)*",
        r"((ab)?)*",
        r"^(([a-z])+.)+[A-Z]",
    ]
    SAFE = [
        r"@corp\.example\.com$",
        r"\d{3}-\d{4}",
        r"^[A-Z]{2,6}$",
        r"(GET|POST|PUT)",
        r"(?:GET|POST)+",
        r"[\w.+-]+@[\w-]+\.[\w.-]+",
        r"(\d{1,3}\.){3}\d{1,3}",
        r"(ab?)*",
        r"(a|b)*",
        r"(?>a+)+",
        r"(a*+)*",
    ]

    def test_dangerous_patterns_rejected(self):
        for pattern in self.DANGEROUS:
            with self.subTest(pattern=pattern):
                with self.assertRaises(RegexSafetyError):
                    Regex("f", pattern)

    def test_safe_patterns_accepted(self):
        for pattern in self.SAFE:
            with self.subTest(pattern=pattern):
                Regex("f", pattern)  # 不抛异常即通过

    def test_dangerous_pattern_via_dsl_has_position(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one(r'when email regex "(a+)+" -> on' + "\n")
        self.assertEqual(cm.exception.line, 2)
        self.assertEqual(cm.exception.col, 18)

    def test_invalid_regex_via_dsl(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one(r'when email regex "(" -> on' + "\n")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 18))

    def test_regex_requires_quoted_string(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one("when email regex corp -> on\n")
        self.assertEqual(cm.exception.line, 2)
        self.assertIn("regex 需要带引号的字符串取值", cm.exception.message)


class TestNotCombinator(unittest.TestCase):
    def test_not_basic(self):
        engine = compile_one("when not(plan eq pro) -> on\n")
        self.assertTrue(engine.evaluate("t", {"plan": "free"}).enabled)
        self.assertFalse(engine.evaluate("t", {"plan": "pro"}).enabled)

    def test_not_missing_field_is_hit(self):
        # ne 对缺失字段判 miss；not(eq ...) 对缺失字段应判命中
        engine = compile_one("when not(vip eq true) -> on\n")
        self.assertTrue(engine.evaluate("t", {}).enabled)
        self.assertFalse(engine.evaluate("t", {"vip": False}).enabled)
        self.assertFalse(engine.evaluate("t", {"vip": True}).enabled)

    def test_not_nested_any_depth(self):
        engine = compile_one(
            "when not(and(not(age ge 18), country eq CN)) -> on\n")
        # not(and(not(>=18), CN))：CN 且未成年 -> False；其余 True
        self.assertFalse(
            engine.evaluate("t", {"age": 10, "country": "CN"}).enabled)
        self.assertTrue(
            engine.evaluate("t", {"age": 20, "country": "CN"}).enabled)
        self.assertTrue(
            engine.evaluate("t", {"age": 10, "country": "US"}).enabled)

    def test_not_with_regex(self):
        engine = compile_one(
            r'when not(email regex "@corp\.example\.com$") -> on' + "\n")
        self.assertFalse(
            engine.evaluate("t", {"email": "a@corp.example.com"}).enabled)
        self.assertTrue(
            engine.evaluate("t", {"email": "a@other.example.com"}).enabled)

    def test_not_in_table(self):
        from flagr import COMBINATOR_TABLE
        self.assertIs(COMBINATOR_TABLE["not"], Not)

    def test_not_describe(self):
        engine = compile_one("when not(plan eq pro) -> on\n")
        self.assertEqual(
            engine.spec("t").rules[0].matcher.describe(),
            'not(plan eq "pro")')

    def test_not_arity(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one("when not() -> on\n")
        self.assertEqual(cm.exception.line, 2)
        self.assertEqual(cm.exception.col, 10)
        with self.assertRaises(RuleCompileError) as cm2:
            compile_one("when not(a eq 1, b eq 2) -> on\n")
        self.assertIn("not 只接受 1 个参数", cm2.exception.message)

    def test_not_without_paren_still_a_field(self):
        # 旧语法兼容：not 后不跟 ( 时仍按字段名解析
        engine = compile_one("when not eq true -> on\n")
        self.assertTrue(engine.evaluate("t", {"not": True}).enabled)


class TestThreadSafety(unittest.TestCase):
    def test_shared_engine_concurrent_evaluation(self):
        engine = compile_one(
            r'when and(email regex "@(corp|example)\.com$", '
            r"not(age lt 18)) -> on" + "\n")
        contexts = [
            {"email": "a@corp.com", "age": 30},
            {"email": "b@example.com", "age": 12},
            {"email": "c@other.com", "age": 40},
            {},
        ]
        expected = [engine.evaluate("t", ctx).enabled for ctx in contexts]
        errors = []

        def worker():
            try:
                for _ in range(2000):
                    for ctx, want in zip(contexts, expected):
                        if engine.evaluate("t", ctx).enabled != want:
                            errors.append("mismatch")
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
