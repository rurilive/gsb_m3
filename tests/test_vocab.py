"""词表行为的锁定测试。"""

import unittest

from bytetok.vocab import Vocabulary


class TestVocabulary(unittest.TestCase):
    def test_initial_size_and_byte_mapping(self):
        vocab = Vocabulary()
        self.assertEqual(vocab.size(), 256)
        self.assertEqual(len(vocab), 256)
        self.assertEqual(vocab.token(0), b"\x00")
        self.assertEqual(vocab.token(255), b"\xff")
        self.assertEqual(vocab.token_id(b"a"), 97)

    def test_token_out_of_range(self):
        vocab = Vocabulary()
        for bad in (-1, 256, 9999):
            with self.assertRaises(KeyError):
                vocab.token(bad)

    def test_token_id_unknown_raises(self):
        vocab = Vocabulary()
        with self.assertRaises(KeyError):
            vocab.token_id(b"ab")

    def test_add_appends_and_returns_id(self):
        vocab = Vocabulary()
        self.assertEqual(vocab.add(b"ab"), 256)
        self.assertEqual(vocab.add(b"abc"), 257)
        self.assertEqual(vocab.size(), 258)
        self.assertEqual(vocab.token(256), b"ab")
        self.assertEqual(vocab.token_id(b"abc"), 257)

    def test_add_existing_is_idempotent(self):
        vocab = Vocabulary()
        self.assertEqual(vocab.add(b"a"), 97)
        self.assertEqual(vocab.add(b"ab"), 256)
        self.assertEqual(vocab.add(b"ab"), 256)
        self.assertEqual(vocab.size(), 257)

    def test_add_rejects_empty(self):
        vocab = Vocabulary()
        with self.assertRaises(ValueError):
            vocab.add(b"")

    def test_add_rejects_str(self):
        vocab = Vocabulary()
        with self.assertRaises(TypeError):
            vocab.add("ab")

    def test_contains_and_tokens_snapshot(self):
        vocab = Vocabulary()
        self.assertIn(b"a", vocab)
        self.assertNotIn(b"ab", vocab)
        vocab.add(b"ab")
        self.assertIn(b"ab", vocab)
        snapshot = vocab.tokens()
        self.assertEqual(len(snapshot), 257)
        snapshot.append(b"junk")
        self.assertEqual(vocab.size(), 257)


if __name__ == "__main__":
    unittest.main()
