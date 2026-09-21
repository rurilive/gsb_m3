"""新词法 tokenize 的口径测试。

引号内外转义、注释、续行、坐标分段、错误定位、bytes/乱码鲁棒性，
以及与 shlex posix 口径的随机对拍（分歧只允许已知的两处）。
"""

import random
import shlex
import unittest

from cmdparse import ParseError, tokenize


def words(text):
    return [token.text for token in tokenize(text)]


class TestBasicWords(unittest.TestCase):
    def test_plain_words(self):
        self.assertEqual(words("git status"), ["git", "status"])

    def test_whitespace_runs_collapse(self):
        self.assertEqual(words("  git\t status\r\n"), ["git", "status"])

    def test_blank_input_gives_nothing(self):
        self.assertEqual(words(""), [])
        self.assertEqual(words("   \t\r\n  "), [])

    def test_adjacent_quotes_concatenate(self):
        self.assertEqual(words("x'a'b"), ["xab"])
        self.assertEqual(words("'a'\"b\"c"), ["abc"])

    def test_empty_quotes_are_empty_words(self):
        tokens = tokenize("'' \"\"")
        self.assertEqual([token.text for token in tokens], ["", ""])

    def test_whitespace_only_ascii_four(self):
        # 垂直制表符与换页符不是 shlex 口径的空白，只是普通字符
        self.assertEqual(words("a\vb\fc"), ["a\vb\fc"])
        self.assertEqual(words("a\u3000b"), ["a\u3000b"])


class TestQuotesAndEscapes(unittest.TestCase):
    def test_double_quoted_space_is_one_word(self):
        self.assertEqual(words('echo "a b"'), ["echo", "a b"])

    def test_single_quoted_space_is_one_word(self):
        self.assertEqual(words("echo 'a b'"), ["echo", "a b"])

    def test_single_quotes_keep_everything_verbatim(self):
        self.assertEqual(words(r"'a\b \"c\" $x #y'"), [r'a\b \"c\" $x #y'])

    def test_double_quotes_keep_variable_placeholders(self):
        self.assertEqual(words('"$GREETING ${HOME} `x`"'),
                         ["$GREETING ${HOME} `x`"])

    def test_double_quote_escapes(self):
        self.assertEqual(words(r'"a\"b\\c"'), ['a"b\\c'])

    def test_double_quote_backslash_kept_before_other_chars(self):
        # 与 shlex posix 一致：\$ \` \! \n 的反斜杠原样保留
        self.assertEqual(words(r'"a\$b\`c\!d\ne"'),
                         [r'a\$b\`c\!d\ne'])

    def test_unquoted_backslash_escapes_next_char(self):
        self.assertEqual(words(r"echo a\ b\#c"), ["echo", "a b#c"])

    def test_escaped_quote_and_backslash_outside(self):
        self.assertEqual(words(r"a\"b c\\d"), ['a"b', r"c\d"])

    def test_newline_inside_quotes_stays_in_word(self):
        self.assertEqual(words("'a\nb'"), ["a\nb"])
        self.assertEqual(words('"a\nb"'), ["a\nb"])


class TestComments(unittest.TestCase):
    def test_hash_at_line_start_is_comment(self):
        self.assertEqual(words("# whole line\ncmd"), ["cmd"])

    def test_hash_after_whitespace_is_comment(self):
        self.assertEqual(words("a b # rest of line\nc"),
                         ["a", "b", "c"])

    def test_hash_inside_word_is_literal(self):
        # 与 shlex 的分歧点之一：shlex 会从词中 # 起注释掉
        self.assertEqual(words("echo a#b"), ["echo", "a#b"])

    def test_hash_inside_quotes_is_literal(self):
        self.assertEqual(words("echo 'a#b' \"c#d\""),
                         ["echo", "a#b", "c#d"])

    def test_comment_to_eof(self):
        self.assertEqual(words("a # comment without newline"), ["a"])


class TestLineContinuation(unittest.TestCase):
    def test_unquoted_backslash_newline_continues_word(self):
        # 与 shlex 的分歧点：shlex 会把换行留在词里
        self.assertEqual(words("echo a\\\nb"), ["echo", "ab"])

    def test_backslash_newline_before_word_starts_silently(self):
        self.assertEqual(words("\\\ncmd"), ["cmd"])

    def test_multiple_continuations(self):
        self.assertEqual(words("a\\\nb\\\nc"), ["abc"])

    def test_continuation_does_not_join_across_whitespace(self):
        self.assertEqual(words("a \\\nb"), ["a", "b"])

    def test_continuation_tracks_line_and_column(self):
        tokens = tokenize("a\\\nb")
        token = tokens[0]
        self.assertEqual(token.text, "ab")
        self.assertEqual((token.start.line, token.start.column), (1, 1))
        self.assertEqual((token.end.line, token.end.column), (2, 2))
        self.assertEqual(token.start.offset, 0)
        self.assertEqual(token.end.offset, 4)

    def test_continuation_combos_with_quotes(self):
        self.assertEqual(words("'a'b\\\nc"), ["abc"])
        self.assertEqual(words('a\\\n"b c"'), ["ab c"])
        self.assertEqual(words("'a'\\ b"), ["a b"])
        self.assertEqual(words("\\\n"), [])

    def test_backslash_cr_follows_shlex(self):
        # \<CR> 把 CR 当被转义字符吃进词，后面的 LF 正常分词
        self.assertEqual(words("a\\\r\nb"), ["a\r", "b"])
        self.assertEqual(words("a\r\nb"), ["a", "b"])


class TestPositionsAndSegments(unittest.TestCase):
    def test_token_positions_are_one_based_half_open(self):
        tokens = tokenize("echo a")
        self.assertEqual(tuple(tokens[0].start), (1, 1, 0))
        self.assertEqual(tuple(tokens[0].end), (1, 5, 4))
        self.assertEqual(tuple(tokens[1].start), (1, 6, 5))
        self.assertEqual(tuple(tokens[1].end), (1, 7, 6))

    def test_offsets_slice_back_to_verbatim_source(self):
        source = "git commit -m 'fix parser'"
        for token in tokenize(source):
            self.assertTrue(token.start.offset < token.end.offset
                            or token.text == "")
        token = tokenize(source)[-1]
        self.assertEqual(
            source[token.start.offset:token.end.offset], "'fix parser'")

    def test_segment_kinds_for_mixed_word(self):
        token = tokenize('x"a b"y\'c\'z')[0]
        self.assertEqual(token.text, 'xa bycz')
        kinds = [segment.kind for segment in token.segments]
        self.assertEqual(kinds, ["plain", "double", "plain", "single", "plain"])
        texts = [segment.text for segment in token.segments]
        self.assertEqual(texts, ["x", "a b", "y", "c", "z"])

    def test_quote_segments_span_including_quotes(self):
        source = '"hi"'
        segment = tokenize(source)[0].segments[0]
        self.assertEqual(segment.kind, "double")
        self.assertEqual(source[segment.start.offset:segment.end.offset], '"hi"')

    def test_plain_segment_span_covers_backslash(self):
        source = r"a\ b"
        segment = tokenize(source)[0].segments[0]
        self.assertEqual(segment.kind, "plain")
        self.assertEqual(source[segment.start.offset:segment.end.offset], r"a\ b")
        self.assertEqual(segment.text, "a b")

    def test_second_line_column_counts_from_one(self):
        tokens = tokenize("ab\ncd")
        self.assertEqual((tokens[1].start.line, tokens[1].start.column), (2, 1))

    def test_position_right_after_newline_is_column_one(self):
        tokens = tokenize("'a\nb'\nx")
        token = tokens[0]
        self.assertEqual(tuple(token.start), (1, 1, 0))
        self.assertEqual(tuple(token.end), (2, 3, 5))
        self.assertEqual(tuple(tokens[1].start), (3, 1, 6))

    def test_token_ending_before_newline(self):
        token = tokenize("ab\n")[0]
        self.assertEqual(tuple(token.end), (1, 3, 2))


class TestErrors(unittest.TestCase):
    def test_unclosed_single_quote_points_at_quote(self):
        with self.assertRaises(ParseError) as caught:
            tokenize("echo 'oops")
        error = caught.exception
        self.assertEqual((error.line, error.column), (1, 6))
        self.assertEqual(error.source_line, "echo 'oops")

    def test_unclosed_double_quote_points_at_quote(self):
        with self.assertRaises(ParseError) as caught:
            tokenize('a\n  "oops')
        error = caught.exception
        self.assertEqual((error.line, error.column), (2, 3))
        self.assertEqual(error.source_line, '  "oops')

    def test_dangling_escape_points_at_backslash(self):
        with self.assertRaises(ParseError) as caught:
            tokenize("abc\\")
        error = caught.exception
        self.assertEqual((error.line, error.column), (1, 4))

    def test_dangling_escape_inside_double_quote(self):
        with self.assertRaises(ParseError) as caught:
            tokenize('"ab\\')
        error = caught.exception
        self.assertEqual((error.line, error.column), (1, 4))

    def test_backslash_inside_single_quote_is_not_dangling(self):
        self.assertEqual(words("'ab\\'"), ["ab\\"])

    def test_backslash_newline_at_eof_is_not_dangling(self):
        self.assertEqual(words("a\\\n"), ["a"])

    def test_error_format_renders_caret(self):
        try:
            tokenize("echo 'oops")
        except ParseError as error:
            rendered = error.format().split("\n")
        self.assertEqual(rendered[1], "echo 'oops")
        self.assertEqual(rendered[2], "     ^")


class TestBytesAndGarbage(unittest.TestCase):
    def test_bytes_are_decoded(self):
        self.assertEqual(words(b'echo "a b"'), ["echo", "a b"])

    def test_invalid_utf8_does_not_crash(self):
        tokens = tokenize(b'bad \xff\xfe bytes')
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[1].text.encode("utf-8", "surrogateescape"),
                         b'\xff\xfe')

    def test_bytearray_and_memoryview(self):
        self.assertEqual(words(bytearray(b'ls -l')), ["ls", "-l"])
        self.assertEqual(words(memoryview(b'ls -l')), ["ls", "-l"])

    def test_nul_byte_in_bytes_is_plain_char(self):
        self.assertEqual(words(b'a\x00b'), ["a\x00b"])

    def test_lone_surrogate_str_does_not_crash(self):
        tokens = tokenize("a\udcff b")
        self.assertEqual([token.text for token in tokens], ["a\udcff", "b"])

    def test_other_types_raise_type_error(self):
        for bad in (None, 1, ["a"], object()):
            with self.assertRaises(TypeError):
                tokenize(bad)


class TestShlexCrossCheck(unittest.TestCase):
    PLAIN_CHARS = "abcABC019_-./@%+=:,x?~|;&()<>z"
    SQ_CHARS = 'ab \t$`"\\#\n!'

    def _shlex_words(self, source):
        lexer = shlex.shlex(source, posix=True)
        lexer.whitespace_split = True
        result = []
        try:
            while True:
                token = lexer.get_token()
                if token is None:
                    return result
                result.append(token)
        except ValueError:
            return None

    def _make_word(self, rng):
        parts = []
        for _ in range(rng.randint(1, 4)):
            kind = rng.randint(0, 3)
            if kind == 0:
                parts.append("".join(rng.choice(self.PLAIN_CHARS)
                                   for _ in range(rng.randint(0, 6))))
            elif kind == 1:
                parts.append("'" + "".join(rng.choice(self.SQ_CHARS)
                                           for _ in range(rng.randint(0, 6)))
                             + "'")
            elif kind == 2:
                inside = []
                for _ in range(rng.randint(0, 6)):
                    inside.append(rng.choice(['a', 'b', ' ', '$', '`', '#',
                                              '!', '\\"', '\\\\']))
                parts.append('"' + "".join(inside) + '"')
            else:
                parts.append("".join(rng.choice(["\\ ", "\\\t"])
                               for _ in range(rng.randint(1, 3))))
        return "".join(parts)

    def _make_source(self, rng):
        out = []
        count = rng.randint(0, 8)
        for i in range(count):
            if i:
                out.append(rng.choice([" ", "  ", "\t", " \t", "\n", " \n "]))
                if rng.random() < 0.2:
                    out.append("# 注释 abc #$!x\n")
            out.append(self._make_word(rng))
        return "".join(out)

    def test_random_corpus_matches_word_by_word(self):
        rng = random.Random(20260921)
        mismatches = 0
        checked = 0
        for _ in range(3000):
            source = self._make_source(rng)
            if not source:
                continue
            expected = self._shlex_words(source)
            got = [token.text for token in tokenize(source)]
            checked += 1
            if got != expected:
                mismatches += 1
        self.assertEqual(mismatches, 0,
                         "随机语料 {} 条里有 {} 条与 shlex posix 对不上"
                         .format(checked, mismatches))

    def test_known_divergence_mid_word_hash(self):
        # shlex 把词中 # 之后整行注释掉；我们按 shell 常理当普通字符
        self.assertEqual(self._shlex_words("echo a#b"), ["echo", "a"])
        self.assertEqual(words("echo a#b"), ["echo", "a#b"])

    def test_known_divergence_backslash_newline(self):
        # shlex 不做无引号续行，换行留在词里；我们删掉反斜杠与换行
        self.assertEqual(self._shlex_words("a\\\nb"), ["a\nb"])
        self.assertEqual(words("a\\\nb"), ["ab"])


if __name__ == "__main__":
    unittest.main()
