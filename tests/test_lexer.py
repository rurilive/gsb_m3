"""新词法的口径测试：引号、转义、注释、续行、坐标、报错与输入健壮性。

随机语料那组只在与 shlex posix 口径完全对齐的生成域内逐词对拍；
三处刻意差异（行尾续行、双引号内 \\$/\\` 转义、词内 #）由专门用例锁定，
对拍生成器会避开这些构造。
"""

import random
import shlex
import unittest

from cmdparse import ParseError, tokenize
from cmdparse.lexer import Token


def lex(text):
    return [token.text for token in tokenize(text)]


class TestQuoting(unittest.TestCase):
    def test_double_quoted_space_is_one_word(self):
        self.assertEqual(lex('echo "a b"'), ["echo", "a b"])

    def test_single_quoted_space_is_one_word(self):
        self.assertEqual(lex("echo 'a b'"), ["echo", "a b"])

    def test_empty_quotes_survive(self):
        self.assertEqual(lex('echo ""'), ["echo", ""])
        self.assertEqual(lex("echo ''"), ["echo", ""])
        self.assertEqual(lex('"" ""'), ["", ""])

    def test_adjacent_quoted_and_bare_pieces_join(self):
        self.assertEqual(lex("a''b"), ["ab"])
        self.assertEqual(lex('a""b'), ["ab"])
        self.assertEqual(lex("'a''b'"), ["ab"])
        self.assertEqual(lex('"a""b"'), ["ab"])
        self.assertEqual(lex("ab'cd'ef"), ["abcdef"])

    def test_single_quote_is_fully_literal(self):
        self.assertEqual(lex(r"echo 'a\nb\tc'"), ["echo", r"a\nb\tc"])
        self.assertEqual(lex("echo '$HOME'"), ["echo", "$HOME"])
        self.assertEqual(lex("echo 'a\"b'"), ["echo", 'a"b'])

    def test_double_quote_escapes(self):
        self.assertEqual(lex('echo "a\\"b"'), ["echo", 'a"b'])
        self.assertEqual(lex('echo "a\\\\b"'), ["echo", r"a\b"])

    def test_double_quote_backslash_before_plain_char_stays(self):
        self.assertEqual(lex('echo "a\\nb"'), ["echo", r"a\nb"])
        self.assertEqual(lex('echo "a\\tb"'), ["echo", r"a\tb"])
        self.assertEqual(lex('echo "a\\qb"'), ["echo", r"a\qb"])

    def test_variable_placeholders_are_kept(self):
        self.assertEqual(lex('echo "$GREETING"'), ["echo", "$GREETING"])
        self.assertEqual(lex('echo "${HOME}/bin"'), ["echo", "${HOME}/bin"])
        self.assertEqual(lex('echo "$((1 + 2))"'), ["echo", "$((1 + 2))"])
        self.assertEqual(lex('echo "$GREETING"'), ["echo", "$GREETING"])

    def test_double_quote_dollar_escape_is_literal_dollar(self):
        # 刻意按 shell 常理："\$x" -> $x（shlex 会保留反斜杠，见差异说明）。
        self.assertEqual(lex('echo "\\$x"'), ["echo", "$x"])
        self.assertEqual(lex('echo "\\`x"'), ["echo", "`x"])


class TestBackslash(unittest.TestCase):
    def test_escaped_space_joins_words(self):
        self.assertEqual(lex("echo a\\ b"), ["echo", "a b"])

    def test_escaped_tab_joins_words(self):
        self.assertEqual(lex("echo a\\\tb"), ["echo", "a\tb"])

    def test_escaped_quote_is_literal(self):
        self.assertEqual(lex('echo \\"'), ["echo", '"'])
        self.assertEqual(lex("echo \\'"), ["echo", "'"])

    def test_escaped_hash_is_literal(self):
        self.assertEqual(lex("echo a\\#b"), ["echo", "a#b"])

    def test_dangling_escape_raises(self):
        for source in ("\\", "echo a\\", '"a\\'):
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    tokenize(source)


class TestComments(unittest.TestCase):
    def test_hash_at_word_start_comments_to_end_of_line(self):
        self.assertEqual(lex("echo a # note\necho b"),
                         ["echo", "a", "echo", "b"])

    def test_full_line_comment_gives_nothing(self):
        self.assertEqual(lex("# whole line"), [])
        self.assertEqual(lex("   # indented"), [])

    def test_hash_inside_word_is_literal(self):
        # 刻意按 shell 常理：shlex(comments=True) 会把 a#b 注释掉。
        self.assertEqual(lex("echo a#b"), ["echo", "a#b"])
        self.assertEqual(lex("echo x#"), ["echo", "x#"])

    def test_hash_right_after_closing_quote_is_literal(self):
        self.assertEqual(lex('echo "a"#b'), ["echo", "a#b"])

    def test_hash_inside_quotes_is_literal(self):
        self.assertEqual(lex('echo "a#b"'), ["echo", "a#b"])
        self.assertEqual(lex("echo 'a#b'"), ["echo", "a#b"])


class TestLineContinuation(unittest.TestCase):
    def test_backslash_newline_joins_words(self):
        # 刻意按 shell 常理：shlex 会在词里留一个真实换行。
        self.assertEqual(lex("echo a\\\nb"), ["echo", "ab"])

    def test_backslash_newline_between_words_is_invisible(self):
        self.assertEqual(lex("a\\\nb c"), ["ab", "c"])

    def test_backslash_newline_inside_double_quote(self):
        self.assertEqual(lex('echo "a\\\nb"'), ["echo", "ab"])

    def test_standalone_continuation_emits_nothing(self):
        self.assertEqual(lex("a\\\n"), ["a"])
        self.assertEqual(lex("\\\n"), [])

    def test_newline_inside_single_quote_is_literal(self):
        self.assertEqual(lex("echo 'a\nb'"), ["echo", "a\nb"])

    def test_newline_inside_double_quote_is_literal(self):
        self.assertEqual(lex('echo "a\nb"'), ["echo", "a\nb"])


class TestWhitespace(unittest.TestCase):
    def test_blank_inputs_give_nothing(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize("   \t\r\n  "), [])

    def test_runs_of_ascii_whitespace_collapse(self):
        self.assertEqual(lex("\t  git \n status\r\n"),
                         ["git", "status"])

    def test_vertical_form_feed_and_ideographic_space_are_plain(self):
        self.assertEqual(lex("echo a\fb"), ["echo", "a\fb"])
        self.assertEqual(lex("echo a\vb"), ["echo", "a\vb"])
        self.assertEqual(lex("a\u3000b"), ["a\u3000b"])
        self.assertEqual(lex("a\u00a0b"), ["a\u00a0b"])


class TestPositions(unittest.TestCase):
    def test_plain_token_positions(self):
        tokens = tokenize("echo  a")
        self.assertEqual(tokens, [
            Token("echo", 1, 1, 1, 5),
            Token("a", 1, 7, 1, 8),
        ])

    def test_quoted_span_covers_the_quotes(self):
        tokens = tokenize('echo "a b"')
        self.assertEqual(
            (tokens[1].start_line, tokens[1].start_column,
             tokens[1].end_line, tokens[1].end_column),
            (1, 6, 1, 11),
        )
        self.assertEqual(tokens[1].source_slice('echo "a b"'), '"a b"')

    def test_escaped_space_span_covers_backslash(self):
        tokens = tokenize("echo a\\ b")
        self.assertEqual(tokens[1].source_slice("echo a\\ b"), "a\\ b")
        self.assertEqual(
            (tokens[1].start_column, tokens[1].end_column), (6, 10)
        )

    def test_positions_on_multiple_lines(self):
        tokens = tokenize("a\nbc\n d")
        self.assertEqual(
            [(t.text, t.start_line, t.start_column, t.end_line, t.end_column)
             for t in tokens],
            [("a", 1, 1, 1, 2),
             ("bc", 2, 1, 2, 3),
             ("d", 3, 2, 3, 3)],
        )

    def test_continuation_span_includes_the_backslash_newline(self):
        source = "echo a\\\nb"
        tokens = tokenize(source)
        self.assertEqual(tokens[1].text, "ab")
        self.assertEqual(
            (tokens[1].start_line, tokens[1].start_column,
             tokens[1].end_line, tokens[1].end_column),
            (1, 6, 2, 2),
        )
        self.assertEqual(tokens[1].source_slice(source), "a\\\nb")

    def test_unicode_counts_by_code_point(self):
        tokens = tokenize("汉字 ab")
        self.assertEqual((tokens[0].start_line, tokens[0].start_column,
                          tokens[0].end_line, tokens[0].end_column),
                         (1, 1, 1, 3))
        self.assertEqual(
            (tokens[1].start_line, tokens[1].start_column,
             tokens[1].end_line, tokens[1].end_column),
            (1, 4, 1, 6)
        )

    def test_carriage_return_counts_as_a_column(self):
        tokens = tokenize("ab\rcd")
        self.assertEqual(lex("ab\rcd"), ["ab", "cd"])
        self.assertEqual(tokens[1].start_column, 4)


class TestParseErrors(unittest.TestCase):
    def test_unterminated_double_quote_points_at_opening_quote(self):
        error = self._error('echo "ab')
        self.assertEqual((error.line, error.column), (1, 6))
        self.assertIn("双引号", error.message)

    def test_unterminated_single_quote_points_at_opening_quote(self):
        error = self._error("echo 'ab")
        self.assertEqual((error.line, error.column), (1, 6))
        self.assertIn("单引号", error.message)

    def test_dangling_backslash_points_at_backslash(self):
        error = self._error("echo a\\")
        self.assertEqual((error.line, error.column), (1, 7))

    def test_dangling_backslash_inside_double_quote(self):
        error = self._error('echo "ab\\')
        self.assertEqual((error.line, error.column), (1, 9))

    def test_error_position_on_later_line(self):
        error = self._error("echo ok\nrm 'x")
        self.assertEqual((error.line, error.column), (2, 4))
        self.assertEqual(error.source_line, "rm 'x")

    def test_error_format_renders_caret(self):
        error = self._error("echo a\\")
        self.assertEqual(
            error.format().split("\n"),
            ["反斜杠后面没有可转义的字符（第 1 行第 7 列）",
             "echo a\\", "      ^"],
        )

    @staticmethod
    def _error(source):
        try:
            tokenize(source)
        except ParseError as error:
            return error
        self.fail("应当抛 ParseError: {!r}".format(source))


class TestBytesAndGarbage(unittest.TestCase):
    def test_bytes_are_utf8_decoded(self):
        self.assertEqual(
            lex("echo 汉字".encode("utf-8")),
            ["echo", "汉字"],
        )

    def test_undecodable_bytes_become_replacement_char(self):
        tokens = tokenize(b'echo "a b" \xff\xfe done')
        self.assertEqual(tokens[0].text, "echo")
        self.assertEqual(tokens[1].text, "a b")
        self.assertIn("\ufffd", tokens[2].text)
        self.assertEqual(tokens[3].text, "done")

    def test_bytes_with_unclosed_quote_raise_not_crash(self):
        with self.assertRaises(ParseError):
            tokenize(b'echo "abc')

    def test_nul_is_an_ordinary_character_in_the_lexer(self):
        self.assertEqual(lex("echo a\x00b"), ["echo", "a\x00b"])

    def test_non_str_non_bytes_raises_type_error(self):
        for bad in (None, 1, 3.2, ["x"], object()):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    tokenize(bad)


class TestShlexCrossCheck(unittest.TestCase):
    """在与 shlex posix 完全对齐的生成域内逐词、逐报错对拍。"""

    ALPHABET = (
        list("abcXYZ019_-.,/:=@%+;|*()[]{}~<>!^&")
        + ["$", "`", " ", "\t", "汉", "\u3000", "\v", "\f"]
    )

    def _word_char(self):
        return random.choice([c for c in self.ALPHABET if c not in ("#",)])

    def _word(self):
        parts = []
        for _ in range(random.randint(1, 4)):
            kind = random.random()
            if kind < 0.45:
                parts.append(self._word_char())
            elif kind < 0.72:
                body = "".join(
                    random.choice([c for c in self.ALPHABET
                                   if c not in ("'", "\n")])
                    for _ in range(random.randint(0, 5))
                )
                if random.random() < 0.08:
                    return "'" + body, True
                parts.append("'" + body + "'")
            elif kind < 0.92:
                body = "".join(
                    random.choice(['\\"', "\\\\"])
                    if random.random() < 0.2
                    else random.choice([c for c in self.ALPHABET
                                       if c not in ('"', "\\", "\n")])
                    for _ in range(random.randint(0, 5))
                )
                if random.random() < 0.08:
                    return '"' + body, True
                parts.append('"' + body + '"')
            else:
                parts.append("\\" + random.choice(
                    [c for c in self.ALPHABET if c != "\n"]))
        return "".join(parts), False

    def _stream(self):
        chunks = []
        at_word_start = True
        for _ in range(random.randint(1, 12)):
            if at_word_start and random.random() < 0.12:
                chunks.append("#")
                chunks.extend(
                    random.choice([c for c in self.ALPHABET if c != "\n"])
                    for _ in range(random.randint(0, 5))
                )
                if random.random() < 0.5:
                    chunks.append("\n")
                    at_word_start = True
                else:
                    at_word_start = False
                continue
            if random.random() < 0.25:
                chunks.append(random.choice(
                    [" ", "\t", "\n", "  ", "\t ", "   "]))
                at_word_start = True
                continue
            word, broken = self._word()
            chunks.append(word)
            if broken:
                return "".join(chunks)
            at_word_start = False
            if random.random() < 0.08:
                chunks.append("\\")
                return "".join(chunks)
        return "".join(chunks)

    def test_random_streams_match_shlex_word_for_word(self):
        random.seed(20260921)
        for _ in range(3000):
            source = self._stream()
            with self.subTest(source=source):
                try:
                    tokens = tokenize(source)
                    mine_failed = False
                except ParseError:
                    tokens, mine_failed = None, True
                try:
                    theirs = shlex.split(source, posix=True, comments=True)
                    theirs_failed = False
                except ValueError:
                    theirs, theirs_failed = None, True
                self.assertEqual(mine_failed, theirs_failed)
                if not mine_failed:
                    self.assertEqual(
                        [token.text for token in tokens], theirs
                    )
                    self._assert_spans_round_trip(source, tokens)

    def _assert_spans_round_trip(self, source, tokens):
        previous = (0, 0)
        for token in tokens:
            raw = token.source_slice(source)
            # 区间按坐标切回原文，单独重切只能得到这一个词素（文本相同）。
            self.assertEqual([t.text for t in tokenize(raw)], [token.text])
            position = (token.start_line, token.start_column)
            self.assertGreaterEqual(position, previous)
            previous = position


if __name__ == "__main__":
    unittest.main()
