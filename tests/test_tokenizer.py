"""空白分词口径的锁定测试。"""

import unittest

from cmdparse.tokenizer import split_words


class TestSplitWords(unittest.TestCase):
    def test_plain_words(self):
        self.assertEqual(split_words("git status"), ["git", "status"])

    def test_whitespace_runs_collapse(self):
        self.assertEqual(
            split_words("\t  git \n\n status\r\n"),
            ["git", "status"],
        )

    def test_blank_input_gives_nothing(self):
        self.assertEqual(split_words(""), [])
        self.assertEqual(split_words("  \t\r\n "), [])

    def test_quotes_are_plain_characters(self):
        self.assertEqual(
            split_words("echo \"a b\""),
            ["echo", "\"a", "b\""],
        )
        self.assertEqual(
            split_words("git commit -m 'fix parser'"),
            ["git", "commit", "-m", "'fix", "parser'"],
        )

    def test_backslash_and_hash_are_plain_characters(self):
        self.assertEqual(
            split_words("echo a\\ b #note"),
            ["echo", "a\\", "b", "#note"],
        )

    def test_unicode_spaces_split(self):
        self.assertEqual(split_words("a　b c"), ["a", "b", "c"])

    def test_single_word_kept_verbatim(self):
        self.assertEqual(split_words("  --flag=value  "), ["--flag=value"])

    def test_non_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            split_words(None)
        with self.assertRaises(TypeError):
            split_words(b"ls -l")
        with self.assertRaises(TypeError):
            split_words(["ls", "-l"])


if __name__ == "__main__":
    unittest.main()
