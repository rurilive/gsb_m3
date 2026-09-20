"""IgnoreRules / matched 的行为测试，对齐官方 .gitignore 语义。"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def decide(text, path, is_dir=False, base=""):
    return matched(path, is_dir, [IgnoreRules(text, base)])


def status(text, path, is_dir=False, base=""):
    return decide(text, path, is_dir, base)[0]


class TestParsing(unittest.TestCase):
    def test_comment_lines_are_ignored(self):
        self.assertEqual(status("#foo\n# *.o\n", "#foo"), "allowed")
        self.assertEqual(decide("# *.o\n", "a.o"), ("allowed", None))

    def test_blank_lines_are_ignored(self):
        self.assertEqual(decide("\n   \n", "anything"), ("allowed", None))

    def test_escaped_hash_is_literal(self):
        self.assertEqual(status("\\#note", "#note"), "ignored")
        self.assertEqual(status("\\#note", "note"), "allowed")

    def test_escaped_bang_is_literal(self):
        self.assertEqual(status("\\!important", "!important"), "ignored")
        self.assertEqual(status("\\!important", "important"), "allowed")

    def test_trailing_spaces_stripped(self):
        self.assertEqual(status("foo   ", "foo"), "ignored")
        self.assertEqual(status("foo   ", "foo "), "allowed")

    def test_escaped_trailing_space_kept(self):
        self.assertEqual(status("foo\\ ", "foo "), "ignored")
        self.assertEqual(status("foo\\ ", "foo"), "allowed")


class TestBasicPatterns(unittest.TestCase):
    def test_simple_pattern_at_root(self):
        self.assertEqual(status("*.o", "a.o"), "ignored")
        self.assertEqual(status("*.o", "a.c"), "allowed")

    def test_no_slash_matches_any_depth(self):
        self.assertEqual(status("*.o", "src/x/a.o"), "ignored")
        self.assertEqual(status("temp", "a/b/temp"), "ignored")

    def test_no_slash_matches_basename_only(self):
        self.assertEqual(status("foo", "foo/bar"), "allowed")

    def test_negation_reincludes(self):
        text = "*.o\n!keep.o\n"
        self.assertEqual(status(text, "keep.o"), "allowed")
        self.assertEqual(status(text, "other.o"), "ignored")

    def test_last_matching_rule_wins(self):
        self.assertEqual(status("!a.o\na.o\n", "a.o"), "ignored")
        self.assertEqual(status("a.o\n!a.o\n", "a.o"), "allowed")
        self.assertEqual(status("a.o\n!a.o\na.o\n", "a.o"), "ignored")

    def test_negation_deciding_rule(self):
        result, rule = decide("*.o\n!keep.o\n", "keep.o")
        self.assertEqual(result, "allowed")
        self.assertTrue(rule.negated)
        self.assertEqual(rule.text, "!keep.o")
        self.assertEqual(rule.lineno, 2)

    def test_case_sensitive(self):
        self.assertEqual(status("*.O", "a.o"), "allowed")
        self.assertEqual(status("Readme*", "readme.md"), "allowed")


class TestDirOnly(unittest.TestCase):
    def test_dir_only_matches_directory(self):
        self.assertEqual(status("build/", "build", True), "ignored")

    def test_dir_only_does_not_match_file(self):
        self.assertEqual(decide("build/", "build", False), ("allowed", None))

    def test_dir_only_at_any_depth(self):
        self.assertEqual(status("build/", "src/out/build", True), "ignored")

    def test_dir_only_negation(self):
        text = "build/\n!keep/\n"
        self.assertEqual(status(text, "keep", True), "allowed")
        self.assertEqual(status(text, "keep", False), "allowed")


class TestAnchoring(unittest.TestCase):
    def test_leading_slash_anchors_to_base(self):
        self.assertEqual(status("/foo", "foo"), "ignored")
        self.assertEqual(status("/foo", "sub/foo"), "allowed")

    def test_middle_slash_anchors(self):
        self.assertEqual(status("doc/*.md", "doc/a.md"), "ignored")
        self.assertEqual(status("doc/*.md", "x/doc/a.md"), "allowed")

    def test_anchored_star_does_not_cross_segments(self):
        self.assertEqual(status("doc/*.md", "doc/sub/a.md"), "allowed")
        self.assertEqual(status("a/*/b", "a/x/y/b"), "allowed")


class TestDoubleStar(unittest.TestCase):
    def test_leading_double_star_any_depth(self):
        self.assertEqual(status("**/foo", "foo"), "ignored")
        self.assertEqual(status("**/foo", "a/foo"), "ignored")
        self.assertEqual(status("**/foo", "a/b/foo"), "ignored")

    def test_trailing_double_star_matches_everything_inside(self):
        self.assertEqual(status("abc/**", "abc/x"), "ignored")
        self.assertEqual(status("abc/**", "abc/x/y/z"), "ignored")

    def test_trailing_double_star_needs_content(self):
        self.assertEqual(decide("abc/**", "abc", True), ("allowed", None))

    def test_middle_double_star_zero_levels(self):
        self.assertEqual(status("a/**/b", "a/b"), "ignored")

    def test_middle_double_star_many_levels(self):
        self.assertEqual(status("a/**/b", "a/x/y/b"), "ignored")
        self.assertEqual(status("a/**/b", "a/x/y/c"), "allowed")


class TestWildcards(unittest.TestCase):
    def test_question_mark_single_char(self):
        self.assertEqual(status("a?c", "abc"), "ignored")
        self.assertEqual(status("a?c", "ac"), "allowed")
        self.assertEqual(status("a?c", "abbc"), "allowed")

    def test_char_class(self):
        self.assertEqual(status("[ab].o", "a.o"), "ignored")
        self.assertEqual(status("[ab].o", "c.o"), "allowed")

    def test_char_class_range(self):
        self.assertEqual(status("log.[0-9]", "log.7"), "ignored")
        self.assertEqual(status("log.[0-9]", "log.x"), "allowed")

    def test_char_class_negated(self):
        self.assertEqual(status("[!ab].o", "c.o"), "ignored")
        self.assertEqual(status("[!ab].o", "a.o"), "allowed")

    def test_escaped_star_is_literal(self):
        self.assertEqual(status("\\*.o", "*.o"), "ignored")
        self.assertEqual(status("\\*.o", "a.o"), "allowed")


class TestBasePrefix(unittest.TestCase):
    def test_rules_only_apply_under_base(self):
        self.assertEqual(status("*.o", "src/a.o", base="src"), "ignored")
        self.assertEqual(status("*.o", "other/a.o", base="src"), "allowed")

    def test_base_applies_at_any_depth_below(self):
        self.assertEqual(status("*.o", "src/deep/a.o", base="src"), "ignored")

    def test_anchored_pattern_relative_to_base(self):
        self.assertEqual(status("/gen", "src/gen", base="src"), "ignored")
        self.assertEqual(status("/gen", "gen", base="src"), "allowed")
        self.assertEqual(status("/gen", "src/sub/gen", base="src"), "allowed")


class TestRuleStack(unittest.TestCase):
    def setUp(self):
        self.root = IgnoreRules("*.log\nbuild/\n", "")
        self.src = IgnoreRules("!debug.log\n*.tmp\n", "src")

    def test_deeper_rules_override_shallower(self):
        result, rule = matched("src/debug.log", False, [self.root, self.src])
        self.assertEqual(result, "allowed")
        self.assertIs(rule, self.src.rules[0])

    def test_shallower_rule_applies_when_deeper_silent(self):
        result, rule = matched("src/error.log", False, [self.root, self.src])
        self.assertEqual(result, "ignored")
        self.assertIs(rule, self.root.rules[0])

    def test_deeper_file_scoped_to_its_tree(self):
        self.assertEqual(
            matched("other/x.tmp", False, [self.root, self.src]),
            ("allowed", None),
        )

    def test_dir_only_from_root_prunes_nested_path(self):
        self.assertEqual(matched("build", True, [self.root, self.src])[0], "ignored")

    def test_no_hit_returns_allowed_none(self):
        self.assertEqual(
            matched("main.py", False, [self.root, self.src]),
            ("allowed", None),
        )

    def test_empty_stack(self):
        self.assertEqual(matched("a.o", False, []), ("allowed", None))


if __name__ == "__main__":
    unittest.main()
