"""IgnoreRules / matched 的 .gitignore 语义测试（对齐 git check-ignore）。"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def rules(text, base=""):
    return IgnoreRules(text, base)


def judge(text, relpath, is_dir=False, base=""):
    return matched(relpath, is_dir, [rules(text, base)])


class TestParsing(unittest.TestCase):
    def test_comments_and_blank_lines_are_skipped(self):
        r = rules("# comment\n\n   \n*.o\n")
        self.assertEqual(len(r.rules), 1)
        self.assertEqual(r.rules[0].pattern, "*.o")

    def test_escaped_hash_is_literal(self):
        status, rule = judge("\\#readme", "#readme")
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.pattern, "#readme")

    def test_escaped_bang_is_literal(self):
        status, _ = judge("\\!important", "!important")
        self.assertEqual(status, "ignored")

    def test_trailing_spaces_stripped(self):
        status, _ = judge("foo   \n", "foo")
        self.assertEqual(status, "ignored")

    def test_escaped_trailing_space_kept(self):
        status, _ = judge("foo\\ \n", "foo ")
        self.assertEqual(status, "ignored")
        status, _ = judge("foo\\ \n", "foo")
        self.assertEqual(status, "allowed")

    def test_no_hit_returns_allowed_none(self):
        self.assertEqual(judge("*.o", "main.py"), ("allowed", None))


class TestBasicMatching(unittest.TestCase):
    def test_bare_name_matches_any_depth(self):
        self.assertEqual(judge("*.o", "a/b/c.o")[0], "ignored")
        self.assertEqual(judge("*.o", "c.o")[0], "ignored")

    def test_bare_name_matches_dir_and_contents(self):
        self.assertEqual(judge("build", "build", True)[0], "ignored")
        self.assertEqual(judge("build", "build/x.o")[0], "ignored")
        self.assertEqual(judge("build", "src/build/x.o")[0], "ignored")

    def test_dir_only_requires_directory(self):
        self.assertEqual(judge("build/", "build", True)[0], "ignored")
        self.assertEqual(judge("build/", "build", False), ("allowed", None))
        self.assertEqual(judge("build/", "src/build", False), ("allowed", None))

    def test_dir_only_ignores_contents(self):
        status, rule = judge("build/", "build/x.o")
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.pattern, "build")
        self.assertTrue(rule.dir_only)

    def test_leading_slash_anchors_to_base(self):
        self.assertEqual(judge("/foo", "foo")[0], "ignored")
        self.assertEqual(judge("/foo", "sub/foo"), ("allowed", None))

    def test_inner_slash_anchors(self):
        self.assertEqual(judge("doc/*.html", "doc/a.html")[0], "ignored")
        self.assertEqual(judge("doc/*.html", "doc/sub/a.html"), ("allowed", None))
        self.assertEqual(judge("doc/*.html", "sub/doc/a.html"), ("allowed", None))

    def test_star_does_not_cross_segments(self):
        self.assertEqual(judge("a/*", "a/b")[0], "ignored")
        # a/b 是目录即被 a/* 命中，其下内容一并忽略（与 git 一致）
        self.assertEqual(judge("a/*", "a/b/c")[0], "ignored")
        self.assertEqual(judge("a/*/d", "a/b/c/d"), ("allowed", None))

    def test_question_mark_and_case(self):
        self.assertEqual(judge("?.o", "a.o")[0], "ignored")
        self.assertEqual(judge("?.o", "ab.o"), ("allowed", None))
        self.assertEqual(judge("*.O", "a.o"), ("allowed", None))


class TestDoubleStar(unittest.TestCase):
    def test_leading_double_star(self):
        text = "**/foo"
        self.assertEqual(judge(text, "foo")[0], "ignored")
        self.assertEqual(judge(text, "a/foo")[0], "ignored")
        self.assertEqual(judge(text, "a/b/foo")[0], "ignored")
        self.assertEqual(judge(text, "a/foobar"), ("allowed", None))

    def test_trailing_double_star(self):
        text = "abc/**"
        self.assertEqual(judge(text, "abc/x")[0], "ignored")
        self.assertEqual(judge(text, "abc/x/y")[0], "ignored")
        self.assertEqual(judge(text, "abc", True), ("allowed", None))
        self.assertEqual(judge(text, "abcd/x"), ("allowed", None))

    def test_middle_double_star_zero_or_more(self):
        text = "a/**/b"
        self.assertEqual(judge(text, "a/b")[0], "ignored")
        self.assertEqual(judge(text, "a/x/b")[0], "ignored")
        self.assertEqual(judge(text, "a/x/y/b")[0], "ignored")
        self.assertEqual(judge(text, "a/x/y")[0], "allowed")
        self.assertEqual(judge(text, "x/a/b"), ("allowed", None))

    def test_double_star_dir_only_anywhere(self):
        self.assertEqual(judge("**/tmp/", "x/tmp/y")[0], "ignored")
        self.assertEqual(judge("**/tmp/", "tmp", True)[0], "ignored")
        self.assertEqual(judge("**/tmp/", "x/tmp", False), ("allowed", None))


class TestNegation(unittest.TestCase):
    def test_later_rule_wins(self):
        self.assertEqual(judge("*.log\n!keep.log", "keep.log")[0], "allowed")
        self.assertEqual(judge("!keep.log\n*.log", "keep.log")[0], "ignored")

    def test_negation_returns_deciding_rule(self):
        status, rule = judge("*.log\n!keep.log", "keep.log")
        self.assertEqual(status, "allowed")
        self.assertIsNotNone(rule)
        self.assertTrue(rule.negated)
        self.assertEqual(rule.pattern, "keep.log")

    def test_other_files_still_ignored(self):
        self.assertEqual(judge("*.log\n!keep.log", "debug.log")[0], "ignored")

    def test_cannot_reinclude_under_excluded_parent(self):
        text = "build/\n!build/keep.txt"
        status, rule = judge(text, "build/keep.txt")
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.pattern, "build")

    def test_negating_the_dir_reincludes_contents(self):
        self.assertEqual(judge("build/\n!build/", "build/x.o"), ("allowed", None))


class TestBaseAndStack(unittest.TestCase):
    def test_base_scopes_rules(self):
        r = rules("*.o", base="src")
        self.assertEqual(matched("src/a.o", False, [r])[0], "ignored")
        self.assertEqual(matched("other/a.o", False, [r]), ("allowed", None))
        self.assertEqual(matched("src", True, [r]), ("allowed", None))

    def test_anchored_relative_to_base(self):
        r = rules("/gen/", base="src")
        self.assertEqual(matched("src/gen/x", False, [r])[0], "ignored")
        self.assertEqual(matched("src/sub/gen/x", False, [r]), ("allowed", None))

    def test_deeper_file_wins(self):
        stack = [rules("*.o"), rules("!keep.o", base="src")]
        status, rule = matched("src/keep.o", False, stack)
        self.assertEqual(status, "allowed")
        self.assertEqual(rule.base, "src")
        self.assertEqual(matched("keep.o", False, stack)[0], "ignored")
        self.assertEqual(matched("src/x.o", False, stack)[0], "ignored")

    def test_deeper_file_cannot_reinclude_under_excluded_parent(self):
        stack = [rules("build/"), rules("!x.o", base="build")]
        status, rule = matched("build/x.o", False, stack)
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.base, "")

    def test_deeper_file_ignores_after_dir_reincluded(self):
        stack = [rules("build/\n!build/"), rules("*.o", base="build")]
        self.assertEqual(matched("build/x.o", False, stack)[0], "ignored")
        self.assertEqual(matched("build/x.c", False, stack), ("allowed", None))

    def test_deciding_rule_is_last_match(self):
        status, rule = judge("*.o\nx.o\n", "x.o")
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.pattern, "x.o")
        self.assertEqual(rule.lineno, 2)


if __name__ == "__main__":
    unittest.main()
