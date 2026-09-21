"""命令流文档的切行、分词与拒收口径测试。"""

import unittest

from cmdparse.diagnostics import ParseError
from cmdparse.document import CommandDocument


class TestLineSplitting(unittest.TestCase):
    def test_lines_counted_by_newline(self):
        document = CommandDocument("ls\npwd")
        self.assertEqual(document.line_count(), 2)
        self.assertEqual(document.line(1), "ls")
        self.assertEqual(document.line(2), "pwd")

    def test_trailing_newline_makes_an_empty_line(self):
        document = CommandDocument("ls\n")
        self.assertEqual(document.line_count(), 2)
        self.assertEqual(document.line(2), "")

    def test_blank_document_is_one_empty_line(self):
        document = CommandDocument("")
        self.assertEqual(document.line_count(), 1)
        self.assertEqual(document.line(1), "")

    def test_iter_lines_numbers_from_one(self):
        document = CommandDocument("a\n\nb")
        self.assertEqual(list(document.iter_lines()), [(1, "a"), (2, ""), (3, "b")])

    def test_line_out_of_range(self):
        document = CommandDocument("ls")
        with self.assertRaises(IndexError):
            document.line(2)
        with self.assertRaises(IndexError):
            document.line(0)
        with self.assertRaises(TypeError):
            document.line(True)

    def test_non_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            CommandDocument(b"ls\npwd")


class TestCommands(unittest.TestCase):
    def test_blank_lines_are_skipped(self):
        document = CommandDocument("ls -l\n\n\n pwd \n")
        self.assertEqual(document.commands(), [(1, ["ls", "-l"]), (4, ["pwd"])])

    def test_word_count_sums_non_blank_lines(self):
        document = CommandDocument("ls -l\n\npwd\n")
        self.assertEqual(document.word_count(), 3)

    def test_quotes_are_split_apart(self):
        document = CommandDocument("rm -rf build \"old logs\"")
        self.assertEqual(
            document.commands(),
            [(1, ["rm", "-rf", "build", "\"old", "logs\""])],
        )


class TestNulRejection(unittest.TestCase):
    def test_first_line_nul_points_at_column(self):
        with self.assertRaises(ParseError) as caught:
            CommandDocument("ab\x00cd")
        error = caught.exception
        self.assertEqual((error.line, error.column), (1, 3))

    def test_later_line_nul_counts_from_line_start(self):
        with self.assertRaises(ParseError) as caught:
            CommandDocument("ls\nrm \x00rf /tmp")
        error = caught.exception
        self.assertEqual((error.line, error.column), (2, 4))
        self.assertEqual(error.source_line, "rm \x00rf /tmp")

    def test_nul_at_line_head(self):
        with self.assertRaises(ParseError) as caught:
            CommandDocument("ls\n\x00")
        self.assertEqual((caught.exception.line, caught.exception.column), (2, 1))

    def test_error_format_renders_caret(self):
        try:
            CommandDocument("ls\nrm \x00rf /tmp")
        except ParseError as error:
            rendered = error.format().split("\n")
        self.assertEqual(
            rendered,
            ["命令流里混进了 NUL 字节，先清掉再贴（第 2 行第 4 列）",
             "rm \x00rf /tmp",
             "   ^"],
        )


if __name__ == "__main__":
    unittest.main()
