"""quote_word 规范引用的口径测试：往返、shlex.quote 一致、边界。"""

import shlex
import unittest

from cmdparse import quote_word, tokenize

WORDS = [
    "", "abc", "a b", "a'b", 'a"b', "$HOME", "a\\b", "a#b",
    "汉字", "a　b", "a\nb", "tab\there", "x;y", "a(b)", "a*b",
    "a[b]", "a{b}", "a|b", "a&b", "a>b", "a<b", "~x",
    "a=b", "--flag=x", "path/to/x", "a:b", "%s", "@host", "a+b",
    "it's a \"quote\"", "'", '"', "\\", "#hash", "x y ' z",
]


class TestQuoteWord(unittest.TestCase):
    def test_empty_string_survives(self):
        self.assertEqual(quote_word(""), "''")
        self.assertEqual(
            [token.text for token in tokenize(quote_word(""))], [""]
        )

    def test_round_trip_every_sample(self):
        for word in WORDS:
            with self.subTest(word=word):
                quoted = quote_word(word)
                tokens = tokenize(quoted)
                self.assertEqual(len(tokens), 1)
                self.assertEqual(tokens[0].text, word)

    def test_joined_stream_round_trips(self):
        line = " ".join(quote_word(word) for word in WORDS)
        self.assertEqual(
            [token.text for token in tokenize(line)], WORDS
        )

    def test_matches_shlex_quote(self):
        for word in WORDS:
            with self.subTest(word=word):
                self.assertEqual(quote_word(word), shlex.quote(word))

    def test_safe_words_are_unquoted(self):
        for word in ("abc", "A-z_0", "--flag=x", "a/b/c", "1.2", "a:b@c"):
            self.assertEqual(quote_word(word), word)

    def test_unsafe_words_are_single_quoted(self):
        self.assertEqual(quote_word("a b"), "'a b'")
        self.assertEqual(quote_word("$HOME"), "'$HOME'")
        self.assertEqual(quote_word("a;b"), "'a;b'")
        self.assertEqual(quote_word("a'b"), "'a'\"'\"'b'")

    def test_non_str_raises_type_error(self):
        for bad in (None, b"abc", 1, ["a"]):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    quote_word(bad)


if __name__ == "__main__":
    unittest.main()
