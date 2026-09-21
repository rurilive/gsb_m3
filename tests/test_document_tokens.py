"""CommandDocument.tokens() 与新词法的接线测试；老 commands() 不碰。"""

import unittest

from cmdparse import CommandDocument, ParseError


class TestTokens(unittest.TestCase):
    def test_tokens_grouped_by_start_line_and_blanks_skipped(self):
        document = CommandDocument('echo "a b"\n\npwd\n')
        grouped = document.tokens()
        self.assertEqual(len(grouped), 2)
        line_one, tokens_one = grouped[0]
        self.assertEqual(line_one, 1)
        self.assertEqual([t.text for t in tokens_one], ["echo", "a b"])
        line_three, tokens_three = grouped[1]
        self.assertEqual(line_three, 3)
        self.assertEqual([t.text for t in tokens_three], ["pwd"])

    def test_continued_line_token_belongs_to_start_line(self):
        document = CommandDocument("tar src/ \\\n  docs/")
        grouped = document.tokens()
        self.assertEqual(len(grouped), 2)
        number, tokens = grouped[0]
        self.assertEqual(number, 1)
        self.assertEqual([t.text for t in tokens], ["tar", "src/"])
        # src/ 后面有空格，续行不粘着：src/ 在第一行收尾，docs/ 落在第二行。
        self.assertEqual((tokens[1].end_line, tokens[1].end_column), (1, 9))
        self.assertEqual(
            tokens[1].source_slice("tar src/ \\\n  docs/"), "src/"
        )
        number_two, tokens_two = grouped[1]
        self.assertEqual(number_two, 2)
        self.assertEqual([t.text for t in tokens_two], ["docs/"])
        self.assertEqual(
            (tokens_two[0].start_line, tokens_two[0].start_column), (2, 3)
        )

    def test_glued_continuation_keeps_everything_on_start_line(self):
        document = CommandDocument("tar src/\\\ndocs/")
        grouped = document.tokens()
        self.assertEqual(len(grouped), 1)
        number, tokens = grouped[0]
        self.assertEqual(number, 1)
        self.assertEqual([t.text for t in tokens], ["tar", "src/docs/"])
        self.assertEqual(
            (tokens[1].start_line, tokens[1].end_line), (1, 2)
        )

    def test_quoted_newline_keeps_one_token(self):
        document = CommandDocument("echo 'a\nb'")
        number, tokens = document.tokens()[0]
        self.assertEqual(number, 1)
        self.assertEqual([t.text for t in tokens], ["echo", "a\nb"])

    def test_tokens_cache_is_stable(self):
        document = CommandDocument("echo a b")
        self.assertIs(document.tokens(), document.tokens())

    def test_lexer_error_carries_document_coordinates(self):
        document = CommandDocument("echo ok\nrm 'x")
        with self.assertRaises(ParseError) as caught:
            document.tokens()
        self.assertEqual(
            (caught.exception.line, caught.exception.column), (2, 4)
        )

    def test_legacy_commands_unchanged(self):
        document = CommandDocument('rm -rf build "old logs"')
        self.assertEqual(
            document.commands(),
            [(1, ["rm", "-rf", "build", '"old', 'logs"'])],
        )


if __name__ == "__main__":
    unittest.main()
