"""统计报告口径的测试。"""

import unittest

from cmdparse.document import CommandDocument
from cmdparse.report import summarize, word_frequency


class TestSummarize(unittest.TestCase):
    def test_reports_each_command_line_then_total(self):
        document = CommandDocument("ls -l\n\npwd\n")
        self.assertEqual(
            summarize(document),
            "第 1 行: 2 个词\n第 3 行: 1 个词\n合计: 4 行, 3 个词",
        )

    def test_blank_document_reports_zero(self):
        self.assertEqual(summarize(CommandDocument("")), "合计: 1 行, 0 个词")


class TestWordFrequency(unittest.TestCase):
    def test_ordered_by_count_then_word(self):
        document = CommandDocument("git add a\ngit add b\ngit commit")
        self.assertEqual(
            word_frequency(document),
            [("git", 3), ("add", 2), ("a", 1), ("b", 1), ("commit", 1)],
        )

    def test_top_truncates(self):
        document = CommandDocument("a a b b b c")
        self.assertEqual(word_frequency(document, top=2), [("b", 3), ("a", 2)])

    def test_counts_are_case_sensitive_for_now(self):
        document = CommandDocument("Git git GIT")
        self.assertEqual(
            word_frequency(document),
            [("GIT", 1), ("Git", 1), ("git", 1)],
        )

    def test_negative_top_is_rejected(self):
        document = CommandDocument("ls")
        with self.assertRaises(ValueError):
            word_frequency(document, top=-1)


if __name__ == "__main__":
    unittest.main()
