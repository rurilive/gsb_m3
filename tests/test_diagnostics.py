"""坐标与诊断渲染的口径测试。"""

import unittest

from cmdparse.diagnostics import ParseError, render_caret


class TestParseError(unittest.TestCase):
    def test_defaults_point_at_the_start(self):
        error = ParseError("未闭合引号")
        self.assertEqual((error.line, error.column), (1, 1))
        self.assertEqual(str(error), "未闭合引号")

    def test_bad_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            ParseError("")
        with self.assertRaises(ValueError):
            ParseError("定位越界", line=0)
        with self.assertRaises(ValueError):
            ParseError("定位越界", column=0)
        with self.assertRaises(TypeError):
            ParseError("定位越界", line="2")

    def test_format_without_source_line(self):
        error = ParseError("未闭合引号", line=3, column=12)
        self.assertEqual(error.format(), "未闭合引号（第 3 行第 12 列）")

    def test_format_with_source_line(self):
        error = ParseError("悬空转义", line=1, column=6, source_line="echo abc\\")
        self.assertEqual(
            error.format().split("\n"),
            ["悬空转义（第 1 行第 6 列）", "echo abc\\", "     ^"],
        )


class TestRenderCaret(unittest.TestCase):
    def test_points_at_the_column(self):
        self.assertEqual(render_caret("abc", 1), "^")
        self.assertEqual(render_caret("abc", 3), "  ^")

    def test_width_spans_a_range(self):
        self.assertEqual(render_caret("abc", 2, width=2), " ^^")

    def test_bad_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            render_caret("abc", 0)
        with self.assertRaises(ValueError):
            render_caret("abc", 1, width=0)


if __name__ == "__main__":
    unittest.main()
