"""IgnoreRules / matched 的 .gitignore 语义测试。"""

import unittest

from pathmatch.ignore import IgnoreRules, matched


def stack(*texts):
    """根目录单层规则栈的便捷构造。"""
    return [IgnoreRules(text) for text in texts]


class TestParsing(unittest.TestCase):
    def test_comments_and_blank_lines_are_skipped(self):
        rules = IgnoreRules("# 注释\n\n   \n*.py\n")
        self.assertEqual(len(rules.rules), 1)
        self.assertEqual(rules.rules[0].text, "*.py")

    def test_escaped_hash_is_literal(self):
        status, _ = matched("#note", False, stack("\\#note"))
        self.assertEqual(status, "ignored")

    def test_escaped_bang_is_literal(self):
        status, _ = matched("!important", False, stack("\\!important"))
        self.assertEqual(status, "ignored")

    def test_trailing_spaces_are_stripped(self):
        status, _ = matched("foo", False, stack("foo   "))
        self.assertEqual(status, "ignored")

    def test_escaped_trailing_space_is_kept(self):
        status, _ = matched("foo ", False, stack("foo\\ "))
        self.assertEqual(status, "ignored")

    def test_empty_text_has_no_rules(self):
        self.assertEqual(IgnoreRules("").rules, [])
        self.assertEqual(IgnoreRules("# only a comment\n").rules, [])


class TestMatching(unittest.TestCase):
    def test_basename_matches_at_root(self):
        status, _ = matched("main.py", False, stack("*.py"))
        self.assertEqual(status, "ignored")

    def test_basename_matches_at_any_depth(self):
        status, _ = matched("src/core/main.py", False, stack("*.py"))
        self.assertEqual(status, "ignored")

    def test_basename_does_not_match_other_names(self):
        self.assertEqual(matched("notes.md", False, stack("*.py")), ("allowed", None))

    def test_plain_name_matches_file_and_dir(self):
        rules = stack("build")
        self.assertEqual(matched("build", False, rules)[0], "ignored")
        self.assertEqual(matched("build", True, rules)[0], "ignored")
        self.assertEqual(matched("x/build", True, rules)[0], "ignored")

    def test_dir_only_matches_directory(self):
        status, rule = matched("build", True, stack("build/"))
        self.assertEqual(status, "ignored")
        self.assertTrue(rule.dir_only)

    def test_dir_only_ignores_file_of_same_name(self):
        self.assertEqual(matched("build", False, stack("build/")), ("allowed", None))

    def test_dir_only_covers_contents(self):
        status, rule = matched("build/out.o", False, stack("build/"))
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.text, "build")

    def test_dir_only_at_any_depth(self):
        status, _ = matched("src/build/out.o", False, stack("build/"))
        self.assertEqual(status, "ignored")

    def test_anchored_to_root(self):
        rules = stack("/foo")
        self.assertEqual(matched("foo", False, rules)[0], "ignored")
        self.assertEqual(matched("sub/foo", False, rules), ("allowed", None))

    def test_anchored_middle_slash(self):
        rules = stack("src/*.py")
        self.assertEqual(matched("src/a.py", False, rules)[0], "ignored")
        self.assertEqual(matched("src/sub/a.py", False, rules), ("allowed", None))
        self.assertEqual(matched("other/src/a.py", False, rules), ("allowed", None))

    def test_star_does_not_cross_segments(self):
        rules = stack("a/*.py")
        self.assertEqual(matched("a/b.py", False, rules)[0], "ignored")
        self.assertEqual(matched("a/b/c.py", False, rules), ("allowed", None))

    def test_star_matching_dir_covers_contents(self):
        # a/* 命中目录 a/b，其下内容随父目录一并被忽略（与 git 一致）
        rules = stack("a/*")
        self.assertEqual(matched("a/b/c", False, rules)[0], "ignored")

    def test_question_mark_matches_single_char(self):
        rules = stack("a?c")
        self.assertEqual(matched("abc", False, rules)[0], "ignored")
        self.assertEqual(matched("ac", False, rules), ("allowed", None))

    def test_char_class(self):
        rules = stack("[ab].py")
        self.assertEqual(matched("a.py", False, rules)[0], "ignored")
        self.assertEqual(matched("c.py", False, rules), ("allowed", None))

    def test_negated_char_class(self):
        rules = stack("[!ab].py")
        self.assertEqual(matched("c.py", False, rules)[0], "ignored")
        self.assertEqual(matched("a.py", False, rules), ("allowed", None))

    def test_leading_double_star(self):
        rules = stack("**/foo")
        for path in ("foo", "a/foo", "a/b/foo"):
            self.assertEqual(matched(path, False, rules)[0], "ignored", path)
        self.assertEqual(matched("a/foobar", False, rules), ("allowed", None))

    def test_trailing_double_star(self):
        rules = stack("abc/**")
        self.assertEqual(matched("abc/x", False, rules)[0], "ignored")
        self.assertEqual(matched("abc/x/y", False, rules)[0], "ignored")
        self.assertEqual(matched("abc", True, rules), ("allowed", None))
        self.assertEqual(matched("abcd/x", False, rules), ("allowed", None))

    def test_middle_double_star_matches_zero_or_more_levels(self):
        rules = stack("a/**/b")
        for path in ("a/b", "a/x/b", "a/x/y/b"):
            self.assertEqual(matched(path, False, rules)[0], "ignored", path)
        self.assertEqual(matched("a/x", False, rules), ("allowed", None))
        self.assertEqual(matched("x/b", False, rules), ("allowed", None))

    def test_double_star_inside_segment_is_plain_stars(self):
        rules = stack("a**b")
        self.assertEqual(matched("aZZb", False, rules)[0], "ignored")
        self.assertEqual(matched("a/zb", False, rules), ("allowed", None))


class TestPriority(unittest.TestCase):
    def test_negation_allows(self):
        rules = stack("*.py\n!keep.py")
        status, rule = matched("keep.py", False, rules)
        self.assertEqual(status, "allowed")
        self.assertTrue(rule.negated)
        self.assertEqual(matched("drop.py", False, rules)[0], "ignored")

    def test_later_rule_wins(self):
        self.assertEqual(matched("a.py", False, stack("*.py\n!a.py"))[0], "allowed")
        self.assertEqual(matched("a.py", False, stack("!a.py\n*.py"))[0], "ignored")

    def test_deeper_rules_file_wins(self):
        root = IgnoreRules("*.log")
        sub = IgnoreRules("!keep.log", base="sub")
        rules = [root, sub]
        status, rule = matched("sub/keep.log", False, rules)
        self.assertEqual(status, "allowed")
        self.assertEqual(rule.base, "sub")
        self.assertEqual(matched("sub/other.log", False, rules)[0], "ignored")
        self.assertEqual(matched("keep.log", False, rules)[0], "ignored")

    def test_base_scopes_rules_to_subtree(self):
        rules = [IgnoreRules("*.tmp", base="sub")]
        self.assertEqual(matched("sub/a.tmp", False, rules)[0], "ignored")
        self.assertEqual(matched("sub/x/y.tmp", False, rules)[0], "ignored")
        self.assertEqual(matched("a.tmp", False, rules), ("allowed", None))

    def test_anchored_relative_to_base(self):
        rules = [IgnoreRules("/foo", base="sub")]
        self.assertEqual(matched("sub/foo", False, rules)[0], "ignored")
        self.assertEqual(matched("foo", False, rules), ("allowed", None))
        self.assertEqual(matched("sub/a/foo", False, rules), ("allowed", None))

    def test_cannot_reinclude_under_excluded_dir(self):
        # 与 git 一致：父目录被忽略后，子路径无法用 ! 恢复
        rules = stack("build/\n!build/keep.txt")
        status, rule = matched("build/keep.txt", False, rules)
        self.assertEqual(status, "ignored")
        self.assertEqual(rule.text, "build")

    def test_reinclude_when_parent_not_excluded(self):
        rules = stack("*.txt\n!keep.txt")
        self.assertEqual(matched("sub/keep.txt", False, rules)[0], "allowed")
        self.assertEqual(matched("sub/drop.txt", False, rules)[0], "ignored")

    def test_deciding_rule_identity(self):
        rules = IgnoreRules("*.py\n!keep.py\n")
        status, rule = matched("keep.py", False, [rules])
        self.assertEqual(status, "allowed")
        self.assertIs(rule, rules.rules[1])
        self.assertEqual(rule.text, "keep.py")
        self.assertEqual(rule.lineno, 2)

    def test_no_match_returns_allowed_none(self):
        self.assertEqual(matched("x.py", False, stack("*.md")), ("allowed", None))
        self.assertEqual(matched("x.py", False, []), ("allowed", None))


if __name__ == "__main__":
    unittest.main()
