"""CommandDocument.tokens() 走新词法的文档级测试。"""

import unittest

from cmdparse import CommandDocument, ParseError


class TestDocumentTokens(unittest.TestCase):
    def test_tokens_flat_list_with_text(self):
        document = CommandDocument('echo "a b"\nls -l')
        tokens = document.tokens()
        self.assertEqual([token.text for token in tokens],
                         ["echo", "a b", "ls", "-l"])

    def test_positions_are_over_whole_document(self):
        document = CommandDocument("a\nb")
        second = document.tokens()[1]
        self.assertEqual((second.start.line, second.start.column), (2, 1))
        self.assertEqual(second.start.offset, 2)

    def test_line_continuation_joins_across_lines(self):
        document = CommandDocument("tar src/ \\\n    docs/")
        self.assertEqual(
            [token.text for token in document.tokens()],
            ["tar", "src/", "docs/"])

    def test_unclosed_quote_raises_parse_error(self):
        document = CommandDocument("echo 'oops")
        with self.assertRaises(ParseError):
            document.tokens()

    def test_old_commands_method_unchanged(self):
        document = CommandDocument('rm -rf build "old logs"')
        self.assertEqual(
            document.commands(),
            [(1, ["rm", "-rf", "build", '"old', 'logs"'])],
        )


if __name__ == "__main__":
    unittest.main()
