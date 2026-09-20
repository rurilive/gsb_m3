""".gitignore 风格 IgnoreRules 的行为测试。

对齐 gitignore 官方语义：注释、转义、否定、目录限定、根锚定、
任意层级、``**`` 跨段、父目录排除不可再包含、嵌套规则深者优先。
"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def decide(text, relpath, is_dir=False, stack=None, base=""):
    rulesets = [IgnoreRules(text, base)] if stack is None else stack
    return matched(relpath, is_dir, rulesets)


class TestParsing(unittest.TestCase):
    def test_blank_lines_and_comments_ignored(self):
        rules = IgnoreRules("# comment\n\n   \nfoo\n")
        self.assertEqual([r.pattern for r in rules.rules], ["foo"])

    def test_escaped_hash_and_bang_are_literal(self):
        rules = IgnoreRules(r"\#readme" + "\n" + r"\!important" + "\n")
        self.assertEqual(rules.rules[0].pattern, "#readme")
        self.assertFalse(rules.rules[0].negated)
        self.assertEqual(rules.rules[1].pattern, "!important")
        self.assertFalse(rules.rules[1].negated)

    def test_trailing_spaces_stripped_unless_escaped(self):
        rules = IgnoreRules("foo   \n" + "bar\\ \\ \n")
        self.assertEqual(rules.rules[0].pattern, "foo")
        self.assertEqual(rules.rules[1].pattern, "bar  ")


class TestBasicMatch(unittest.TestCase):
    def test_no_match_returns_allowed_none(self):
        self.assertEqual(decide("foo\n", "bar", False), ("allowed", None))

    def test_simple_pattern_matches(self):
        status, rule = decide("foo\n", "foo", False)
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.pattern, "foo")

    def test_pattern_without_slash_matches_any_depth(self):
        text = "foo\n"
        self.assertEqual(decide(text, "a/foo", False)[0], "ignored")
        self.assertEqual(decide(text, "a/b/foo", True)[0], "ignored")
        self.assertEqual(decide(text, "foobar", False)[0], "allowed")

    def test_slash_anchors_to_base(self):
        text = "/foo\n"
        self.assertEqual(decide(text, "foo", False)[0], "ignored")
        self.assertEqual(decide(text, "a/foo", False)[0], "allowed")

    def test_slash_anywhere_anchors(self):
        text = "a/foo\n"
        self.assertEqual(decide(text, "a/foo", False)[0], "ignored")
        self.assertEqual(decide(text, "x/a/foo", False)[0], "allowed")

    def test_star_does_not_cross_segments(self):
        self.assertEqual(decide("*.log\n", "a.log", False)[0], "ignored")
        self.assertEqual(decide("*.log\n", "x/a.log", False)[0], "ignored")
        self.assertEqual(decide("a/*.log\n", "a/b.log", False)[0], "ignored")
        self.assertEqual(decide("a/*.log\n", "a/x/b.log", False)[0], "allowed")

    def test_question_mark_single_char(self):
        self.assertEqual(decide("a?c\n", "abc", False)[0], "ignored")
        self.assertEqual(decide("a?c\n", "ac", False)[0], "allowed")

    def test_character_class(self):
        self.assertEqual(decide("[ab].txt\n", "a.txt", False)[0], "ignored")
        self.assertEqual(decide("[ab].txt\n", "c.txt", False)[0], "allowed")


class TestDirectoryOnly(unittest.TestCase):
    def test_trailing_slash_only_dirs(self):
        text = "foo/\n"
        self.assertEqual(decide(text, "foo", False)[0], "allowed")
        self.assertEqual(decide(text, "foo", True)[0], "ignored")

    def test_trailing_slash_any_depth(self):
        text = "build/\n"
        self.assertEqual(decide(text, "a/build", True)[0], "ignored")
        self.assertEqual(decide(text, "a/build/x", False)[0], "ignored")


class TestDoubleStar(unittest.TestCase):
    def test_leading_doublestar_any_level(self):
        text = "**/foo\n"
        for p in ("foo", "a/foo", "a/b/foo"):
            self.assertEqual(decide(text, p, False)[0], "ignored", p)
        self.assertEqual(decide(text, "bar", False)[0], "allowed")

    def test_leading_doublestar_with_more_segments(self):
        text = "**/a/b\n"
        self.assertEqual(decide(text, "a/b", False)[0], "ignored")
        self.assertEqual(decide(text, "x/a/b", False)[0], "ignored")

    def test_trailing_doublestar_excludes_contents_not_self(self):
        text = "a/**\n"
        self.assertEqual(decide(text, "a", True)[0], "allowed")
        self.assertEqual(decide(text, "a/f", False)[0], "ignored")
        self.assertEqual(decide(text, "a/x/y", False)[0], "ignored")

    def test_middle_doublestar_zero_or_more(self):
        text = "a/**/b\n"
        self.assertEqual(decide(text, "a/b", False)[0], "ignored")
        self.assertEqual(decide(text, "a/x/b", False)[0], "ignored")
        self.assertEqual(decide(text, "a/x/y/b", False)[0], "ignored")
        self.assertEqual(decide(text, "c/b", False)[0], "allowed")

    def test_lone_doublestar_matches_everything(self):
        text = "**\n"
        self.assertEqual(decide(text, "x", False)[0], "ignored")
        self.assertEqual(decide(text, "a/b/c", False)[0], "ignored")


class TestNegation(unittest.TestCase):
    def test_later_negation_reincludes(self):
        text = "*.log\n!keep.log\n"
        status, rule = decide(text, "keep.log", False)
        self.assertEqual(status, "allowed")
        self.assertTrue(rule.negated)

    def test_later_positive_reignores(self):
        text = "!keep.log\n*.log\n"
        self.assertEqual(decide(text, "keep.log", False)[0], "ignored")

    def test_negation_same_level_as_exclusion(self):
        # a/* 忽略 a 的内容，!a/b 在同一层把目录 b 要回来。
        text = "a/*\n!a/b\n"
        self.assertEqual(decide(text, "a/b", True)[0], "allowed")
        self.assertEqual(decide(text, "a/b/c", False)[0], "allowed")

    def test_cannot_reinclude_file_under_excluded_parent(self):
        # 父目录 a/b 被 a/* 忽略后，更深层的 !a/b/c 无法翻案。
        text = "a/*\n!a/b/c\n"
        self.assertEqual(decide(text, "a/b/c", False)[0], "ignored")

    def test_negation_order_within_file(self):
        self.assertEqual(
            decide("!a/b\na/*\n", "a/b/c", False)[0], "ignored"
        )

    def test_excluded_dir_propagates(self):
        text = "foo\n"
        self.assertEqual(decide(text, "foo/bar", False)[0], "ignored")
        self.assertEqual(
            decide("foo\n!foo/bar\n", "foo/bar/x", False)[0], "ignored"
        )


class TestRuleStack(unittest.TestCase):
    def setUp(self):
        self.root = IgnoreRules("*.log\nbuild/\n", "")

    def test_deeper_ruleset_wins(self):
        inner = IgnoreRules("!keep.log\n", "src")
        status, rule = matched("src/keep.log", False, [self.root, inner])
        self.assertEqual(status, "allowed")
        self.assertTrue(rule.negated)

    def test_outer_still_applies(self):
        inner = IgnoreRules("!keep.log\n", "src")
        self.assertEqual(
            matched("src/x.log", False, [self.root, inner])[0], "ignored"
        )

    def test_inner_ruleset_under_excluded_dir_ignored(self):
        root = IgnoreRules("a/\n", "")
        inner = IgnoreRules("!b\n", "a")
        self.assertEqual(matched("a/b", False, [root, inner])[0], "ignored")

    def test_inner_ruleset_active_when_only_contents_excluded(self):
        root = IgnoreRules("a/*\n", "")
        inner = IgnoreRules("!b\n", "a")
        self.assertEqual(matched("a/b", False, [root, inner])[0], "allowed")

    def test_stack_order_does_not_matter(self):
        inner = IgnoreRules("!keep.log\n", "src")
        a = matched("src/keep.log", False, [self.root, inner])
        b = matched("src/keep.log", False, [inner, self.root])
        self.assertEqual(a, b)


class TestDecisionRule(unittest.TestCase):
    def test_decision_rule_is_deciding_pattern(self):
        text = "a/**/x\n!a/b/x\n"
        status, rule = decide(text, "a/b/x", False)
        self.assertEqual(status, "allowed")
        self.assertEqual(rule.pattern, "a/b/x")

    def test_repr_shows_negation_and_dir_marker(self):
        rule = IgnoreRules("!foo/\n").rules[0]
        self.assertTrue(rule.negated)
        self.assertTrue(rule.dir_only)
        self.assertEqual(repr(rule), "<Rule !foo/>")


if __name__ == "__main__":
    unittest.main()
