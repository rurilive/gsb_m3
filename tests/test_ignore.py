"""IgnoreRules / matched 的行为测试，对齐 gitignore 官方语义。"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def rules(text, base=""):
    return IgnoreRules(text, base)


class TestParsing(unittest.TestCase):
    def test_comment_and_blank_lines_ignored(self):
        r = rules("# comment\n\n   \n*.log\n")
        self.assertEqual(len(r.rules), 1)

    def test_escaped_hash_is_literal(self):
        r = rules("\\#file\n")
        self.assertEqual(matched("#file", False, [r])[0], "ignored")
        self.assertEqual(matched("other", False, [r])[0], "allowed")

    def test_escaped_bang_is_literal(self):
        r = rules("\\!important.txt\n")
        self.assertEqual(matched("!important.txt", False, [r])[0], "ignored")

    def test_trailing_spaces_stripped(self):
        r = rules("foo.txt   \n")
        self.assertEqual(matched("foo.txt", False, [r])[0], "ignored")
        self.assertEqual(matched("foo.txt ", False, [r])[0], "allowed")

    def test_escaped_trailing_space_kept(self):
        r = rules("foo\\ \n")
        self.assertEqual(matched("foo ", False, [r])[0], "ignored")
        self.assertEqual(matched("foo", False, [r])[0], "allowed")


class TestNegation(unittest.TestCase):
    def test_negation_reincludes(self):
        r = rules("*.log\n!keep.log\n")
        status, rule = matched("keep.log", False, [r])
        self.assertEqual(status, "allowed")
        self.assertIs(rule, r.rules[1])

    def test_later_rule_wins(self):
        r = rules("!a.txt\na.txt\n")
        status, rule = matched("a.txt", False, [r])
        self.assertEqual(status, "ignored")
        self.assertIs(rule, r.rules[1])

    def test_later_negation_wins(self):
        r = rules("*.tmp\n!a.tmp\n")
        self.assertEqual(matched("a.tmp", False, [r])[0], "allowed")
        self.assertEqual(matched("b.tmp", False, [r])[0], "ignored")


class TestDirOnly(unittest.TestCase):
    def setUp(self):
        self.r = rules("build/\n")

    def test_dir_only_matches_dir(self):
        status, rule = matched("build", True, [self.r])
        self.assertEqual(status, "ignored")
        self.assertIs(rule, self.r.rules[0])

    def test_dir_only_skips_file_of_same_name(self):
        self.assertEqual(matched("build", False, [self.r]), ("allowed", None))

    def test_dir_only_covers_contents(self):
        status, rule = matched("build/out.o", False, [self.r])
        self.assertEqual(status, "ignored")
        self.assertIs(rule, self.r.rules[0])

    def test_dir_only_covers_nested_contents(self):
        self.assertEqual(matched("build/x/y.o", False, [self.r])[0], "ignored")


class TestAnchoring(unittest.TestCase):
    def test_slash_anchors_to_base(self):
        r = rules("doc/*.txt\n")
        self.assertEqual(matched("doc/a.txt", False, [r])[0], "ignored")
        self.assertEqual(matched("doc/sub/a.txt", False, [r])[0], "allowed")
        self.assertEqual(matched("x/doc/a.txt", False, [r])[0], "allowed")

    def test_leading_slash_anchors(self):
        r = rules("/build.log\n")
        self.assertEqual(matched("build.log", False, [r])[0], "ignored")
        self.assertEqual(matched("src/build.log", False, [r])[0], "allowed")

    def test_no_slash_matches_any_depth(self):
        r = rules("*.o\n")
        self.assertEqual(matched("a.o", False, [r])[0], "ignored")
        self.assertEqual(matched("a/b/c.o", False, [r])[0], "ignored")

    def test_anchored_relative_to_base(self):
        r = rules("gen/*.py\n", base="src")
        self.assertEqual(matched("src/gen/a.py", False, [r])[0], "ignored")
        self.assertEqual(matched("gen/a.py", False, [r])[0], "allowed")
        self.assertEqual(matched("other/gen/a.py", False, [r])[0], "allowed")

    def test_unanchored_rule_limited_to_base_subtree(self):
        r = rules("*.log\n", base="src")
        self.assertEqual(matched("src/x.log", False, [r])[0], "ignored")
        self.assertEqual(matched("x.log", False, [r])[0], "allowed")


class TestDoubleStar(unittest.TestCase):
    def test_leading_double_star_any_depth(self):
        r = rules("**/tmp\n")
        self.assertEqual(matched("tmp", False, [r])[0], "ignored")
        self.assertEqual(matched("a/tmp", False, [r])[0], "ignored")
        self.assertEqual(matched("a/b/tmp", False, [r])[0], "ignored")

    def test_trailing_double_star_everything_inside(self):
        r = rules("logs/**\n")
        self.assertEqual(matched("logs/a.log", False, [r])[0], "ignored")
        self.assertEqual(matched("logs/a/b/c", False, [r])[0], "ignored")
        self.assertEqual(matched("logs", True, [r])[0], "allowed")

    def test_middle_double_star_zero_dirs(self):
        r = rules("a/**/b\n")
        self.assertEqual(matched("a/b", False, [r])[0], "ignored")

    def test_middle_double_star_many_dirs(self):
        r = rules("a/**/b\n")
        self.assertEqual(matched("a/x/b", False, [r])[0], "ignored")
        self.assertEqual(matched("a/x/y/z/b", False, [r])[0], "ignored")
        self.assertEqual(matched("a/x/y", False, [r])[0], "allowed")

    def test_double_star_not_special_inside_segment(self):
        r = rules("a**b\n")
        self.assertEqual(matched("axxb", False, [r])[0], "ignored")
        self.assertEqual(matched("a/x/b", False, [r])[0], "allowed")


class TestRuleStack(unittest.TestCase):
    def test_deeper_ruleset_wins(self):
        root = rules("*.log\n")
        sub = rules("!keep.log\n", base="src")
        status, rule = matched("src/keep.log", False, [root, sub])
        self.assertEqual(status, "allowed")
        self.assertIs(rule, sub.rules[0])

    def test_deeper_rule_does_not_leak_outside_base(self):
        root = rules("*.log\n")
        sub = rules("!keep.log\n", base="src")
        status, rule = matched("keep.log", False, [root, sub])
        self.assertEqual(status, "ignored")
        self.assertIs(rule, root.rules[0])

    def test_shallower_applies_when_deeper_silent(self):
        root = rules("*.o\n")
        sub = rules("*.log\n", base="src")
        status, rule = matched("src/a.o", False, [root, sub])
        self.assertEqual(status, "ignored")
        self.assertIs(rule, root.rules[0])

    def test_no_match_returns_allowed_none(self):
        self.assertEqual(matched("main.py", False, [rules("*.log\n")]), ("allowed", None))

    def test_empty_stack(self):
        self.assertEqual(matched("anything", False, []), ("allowed", None))


class TestWildcards(unittest.TestCase):
    def test_question_mark_single_char(self):
        r = rules("?.log\n")
        self.assertEqual(matched("a.log", False, [r])[0], "ignored")
        self.assertEqual(matched("ab.log", False, [r])[0], "allowed")

    def test_char_class(self):
        r = rules("[ab].log\n")
        self.assertEqual(matched("a.log", False, [r])[0], "ignored")
        self.assertEqual(matched("c.log", False, [r])[0], "allowed")

    def test_char_class_negation(self):
        r = rules("[!a].log\n")
        self.assertEqual(matched("b.log", False, [r])[0], "ignored")
        self.assertEqual(matched("a.log", False, [r])[0], "allowed")

    def test_star_does_not_cross_segments(self):
        r = rules("a/*.log\n")
        self.assertEqual(matched("a/b.log", False, [r])[0], "ignored")
        self.assertEqual(matched("a/b/c.log", False, [r])[0], "allowed")

    def test_case_sensitive(self):
        r = rules("*.LOG\n")
        self.assertEqual(matched("a.log", False, [r])[0], "allowed")


if __name__ == "__main__":
    unittest.main()
