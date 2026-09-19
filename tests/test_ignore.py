"""IgnoreRules / matched 的行为测试，语义对齐 git check-ignore。"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def decide(relpath, is_dir, stack):
    return matched(relpath, is_dir, stack)[0]


class TestParsing(unittest.TestCase):
    def test_comment_and_blank_lines_ignored(self):
        rules = IgnoreRules("# comment\n\n   \n*.o\n")
        self.assertEqual(len(rules.rules), 1)
        self.assertEqual(rules.rules[0].pattern, "*.o")

    def test_escaped_hash_is_literal(self):
        rules = IgnoreRules("\\#hash.txt\n")
        self.assertEqual(decide("#hash.txt", False, [rules]), "ignored")

    def test_escaped_bang_is_literal(self):
        rules = IgnoreRules("\\!bang.txt\n")
        self.assertEqual(decide("!bang.txt", False, [rules]), "ignored")
        self.assertFalse(rules.rules[0].negated)

    def test_trailing_spaces_stripped(self):
        rules = IgnoreRules("foo.txt   \n")
        self.assertEqual(rules.rules[0].pattern, "foo.txt")

    def test_escaped_trailing_space_kept(self):
        rules = IgnoreRules("sp\\ ace.txt  \n")
        self.assertEqual(decide("sp ace.txt", False, [rules]), "ignored")

    def test_rule_metadata(self):
        rules = IgnoreRules("*.o\n!keep.o\n", base="src")
        first, second = rules.rules
        self.assertEqual((first.lineno, first.negated), (1, False))
        self.assertEqual((second.lineno, second.negated), (2, True))
        self.assertEqual(first.base, "src")


class TestGlobs(unittest.TestCase):
    def setUp(self):
        self.rules = IgnoreRules("*.o\n")

    def test_star_matches_any_level_basename(self):
        self.assertEqual(decide("a.o", False, [self.rules]), "ignored")
        self.assertEqual(decide("x/y/a.o", False, [self.rules]), "ignored")

    def test_star_does_not_cross_segments(self):
        rules = IgnoreRules("src/*.py\n")
        self.assertEqual(decide("src/main.py", False, [rules]), "ignored")
        self.assertEqual(decide("src/pkg/main.py", False, [rules]), "allowed")

    def test_question_mark(self):
        rules = IgnoreRules("a?c.txt\n")
        self.assertEqual(decide("abc.txt", False, [rules]), "ignored")
        self.assertEqual(decide("ac.txt", False, [rules]), "allowed")

    def test_char_class(self):
        rules = IgnoreRules("log.[0-9]\n")
        self.assertEqual(decide("log.7", False, [rules]), "ignored")
        self.assertEqual(decide("log.x", False, [rules]), "allowed")

    def test_negated_char_class(self):
        rules = IgnoreRules("log.[!0-9]\n")
        self.assertEqual(decide("log.x", False, [rules]), "ignored")
        self.assertEqual(decide("log.7", False, [rules]), "allowed")

    def test_case_sensitive(self):
        rules = IgnoreRules("*.O\n")
        self.assertEqual(decide("a.o", False, [rules]), "allowed")


class TestNegation(unittest.TestCase):
    def test_negation_allows(self):
        rules = IgnoreRules("*.o\n!keep.o\n")
        self.assertEqual(decide("keep.o", False, [rules]), "allowed")
        self.assertEqual(decide("a.o", False, [rules]), "ignored")

    def test_later_rule_wins(self):
        rules = IgnoreRules("*.o\n!a.o\na.o\n")
        self.assertEqual(decide("a.o", False, [rules]), "ignored")

    def test_negation_returns_deciding_rule(self):
        rules = IgnoreRules("*.o\n!keep.o\n")
        decision, rule = matched("keep.o", False, [rules])
        self.assertEqual(decision, "allowed")
        self.assertIs(rule, rules.rules[1])


class TestDirOnlyAndAnchoring(unittest.TestCase):
    def test_dir_only_matches_dir_not_file(self):
        rules = IgnoreRules("build/\n")
        self.assertEqual(decide("build", True, [rules]), "ignored")
        self.assertEqual(decide("build", False, [rules]), "allowed")

    def test_dir_only_at_any_level(self):
        rules = IgnoreRules("build/\n")
        self.assertEqual(decide("x/y/build", True, [rules]), "ignored")

    def test_ignored_dir_hides_contents(self):
        rules = IgnoreRules("build/\n")
        self.assertEqual(decide("build/out.o", False, [rules]), "ignored")

    def test_anchored_by_middle_slash(self):
        rules = IgnoreRules("foo/bar\n")
        self.assertEqual(decide("foo/bar", False, [rules]), "ignored")
        self.assertEqual(decide("x/foo/bar", False, [rules]), "allowed")

    def test_anchored_by_leading_slash(self):
        rules = IgnoreRules("/foo\n")
        self.assertEqual(decide("foo", False, [rules]), "ignored")
        self.assertEqual(decide("x/foo", False, [rules]), "allowed")

    def test_non_anchored_matches_any_level(self):
        rules = IgnoreRules("foo\n")
        self.assertEqual(decide("x/y/foo", False, [rules]), "ignored")


class TestDoubleStar(unittest.TestCase):
    def test_leading_double_star(self):
        rules = IgnoreRules("**/foo\n")
        self.assertEqual(decide("foo", False, [rules]), "ignored")
        self.assertEqual(decide("x/y/foo", False, [rules]), "ignored")

    def test_trailing_double_star(self):
        rules = IgnoreRules("doc/**\n")
        self.assertEqual(decide("doc", True, [rules]), "allowed")
        self.assertEqual(decide("doc/a", False, [rules]), "ignored")
        self.assertEqual(decide("doc/a/b", False, [rules]), "ignored")

    def test_middle_double_star_zero_or_more(self):
        rules = IgnoreRules("a/**/b\n")
        self.assertEqual(decide("a/b", False, [rules]), "ignored")
        self.assertEqual(decide("a/x/b", False, [rules]), "ignored")
        self.assertEqual(decide("a/x/y/b", False, [rules]), "ignored")
        self.assertEqual(decide("a/x/y/c", False, [rules]), "allowed")

    def test_double_star_alone_matches_everything(self):
        rules = IgnoreRules("**\n")
        self.assertEqual(decide("a/b/c", False, [rules]), "ignored")


class TestRuleStack(unittest.TestCase):
    def test_deeper_file_wins(self):
        root = IgnoreRules("*.o\n")
        sub = IgnoreRules("!keep.o\n", base="sub")
        self.assertEqual(decide("sub/keep.o", False, [root, sub]), "allowed")
        self.assertEqual(decide("sub/a.o", False, [root, sub]), "ignored")
        self.assertEqual(decide("keep.o", False, [root, sub]), "ignored")

    def test_base_scopes_rules(self):
        sub = IgnoreRules("*.tmp\n", base="sub")
        self.assertEqual(decide("sub/a.tmp", False, [sub]), "ignored")
        self.assertEqual(decide("other/a.tmp", False, [sub]), "allowed")

    def test_deep_negation_cannot_reinclude_under_excluded_dir(self):
        root = IgnoreRules("sub/\n")
        sub = IgnoreRules("!keep.o\n", base="sub")
        self.assertEqual(decide("sub/keep.o", False, [root, sub]), "ignored")

    def test_no_match_returns_allowed_none(self):
        rules = IgnoreRules("*.o\n")
        self.assertEqual(matched("main.py", False, [rules]), ("allowed", None))

    def test_empty_stack(self):
        self.assertEqual(matched("a.o", False, []), ("allowed", None))


if __name__ == "__main__":
    unittest.main()
