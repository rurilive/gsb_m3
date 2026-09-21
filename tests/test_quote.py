"""quote_word 的规范引用与往返测试。"""

import shlex
import unittest

from cmdparse import quote_word, tokenize


class TestQuoteWord(unittest.TestCase):
    def test_empty_string_survives(self):
        self.assertEqual(quote_word(""), "''")
        self.assertEqual([token.text for token in tokenize(quote_word(""))], [""])

    def test_safe_words_unchanged(self):
        for word in ["ls", "-l", "a.b/c_d", "x@%+=:,y-z", "0", "A1"]:
            self.assertEqual(quote_word(word), word)

    def test_spaces_are_quoted(self):
        self.assertEqual(quote_word("a b"), "'a b'")

    def test_single_quote_inside_is_wrapped(self):
        self.assertEqual(quote_word("a'b"), "'a'\"'\"'b'")

    def test_roundtrip_single_words(self):
        for word in ["", " ", "a b", "'", '"', "\\", "$HOME",
                     "a'b\"c\\d", "#hash", "\n\t", "正常路径", "a\x00b"]:
            quoted = quote_word(word)
            tokens = tokenize(quoted)
            self.assertEqual(len(tokens), 1)
            self.assertEqual(tokens[0].text, word)

    def test_roundtrip_joined_command_line(self):
        words = ["", "echo", "hello world", "it's", '$HOME', "a\tb",
                 "#notcomment", "line\nbreak", "x;y", "路径 名"]
        command = " ".join(quote_word(word) for word in words)
        self.assertEqual([token.text for token in tokenize(command)], words)

    def test_matches_shlex_quote(self):
        for word in ["", "safe-word.txt", "a b", "it's", '"q"',
                     "\\back", "$x", "#c", "\n", "中文"]:
            self.assertEqual(quote_word(word), shlex.quote(word))

    def test_non_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            quote_word(b"abc")
        with self.assertRaises(TypeError):
            quote_word(None)


if __name__ == "__main__":
    unittest.main()
