"""分词器行为的锁定测试。"""

import random
import unittest

from bytetok.reference import naive_decode, naive_encode
from bytetok.tokenizer import Tokenizer
from bytetok.vocab import Vocabulary


class TestEncode(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary()
        self.tokenizer = Tokenizer(self.vocab)

    def test_empty_input(self):
        self.assertEqual(self.tokenizer.encode(""), [])
        self.assertEqual(self.tokenizer.encode_bytes(b""), [])

    def test_ascii_is_byte_values(self):
        self.assertEqual(self.tokenizer.encode("abc"), [97, 98, 99])

    def test_multibyte_text(self):
        self.assertEqual(
            self.tokenizer.encode("你好"),
            list("你好".encode("utf-8")),
        )

    def test_matches_naive_reference_on_text(self):
        text = "the quick, brown 狐狸. 跳过了 3 只,懒狗!"
        self.assertEqual(
            self.tokenizer.encode(text),
            naive_encode(self.vocab, text.encode("utf-8")),
        )

    def test_matches_naive_reference_on_random_bytes(self):
        rng = random.Random(20260921)
        for _ in range(100):
            length = rng.randrange(0, 96)
            data = bytes(rng.randrange(0, 256) for _ in range(length))
            self.assertEqual(
                self.tokenizer.encode_bytes(data),
                naive_encode(self.vocab, data),
            )

    def test_encode_rejects_bytes(self):
        with self.assertRaises(TypeError):
            self.tokenizer.encode(b"abc")

    def test_encode_bytes_rejects_str(self):
        with self.assertRaises(TypeError):
            self.tokenizer.encode_bytes("abc")

    def test_segments_view(self):
        self.assertEqual(
            self.tokenizer.segments("a - b"),
            [b"a", b" - ", b"b"],
        )
        with self.assertRaises(TypeError):
            self.tokenizer.segments(b"a - b")


class TestDecode(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary()
        self.tokenizer = Tokenizer(self.vocab)

    def test_roundtrip_text(self):
        for text in ["", "abc", "你好，世界", "a\tb\nc", "🙂🙃"]:
            data = text.encode("utf-8")
            self.assertEqual(self.tokenizer.decode(self.tokenizer.encode(text)), data)

    def test_roundtrip_random_bytes(self):
        rng = random.Random(7)
        for _ in range(200):
            length = rng.randrange(0, 128)
            data = bytes(rng.randrange(0, 256) for _ in range(length))
            ids = self.tokenizer.encode_bytes(data)
            self.assertEqual(self.tokenizer.decode(ids), data)

    def test_decode_matches_naive_reference(self):
        ids = self.tokenizer.encode("mixed 混合 bytes")
        self.assertEqual(
            self.tokenizer.decode(ids),
            naive_decode(self.vocab, ids),
        )

    def test_decode_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.tokenizer.decode([256])

    def test_decode_after_added_token(self):
        self.vocab.add(b"ab")
        self.assertEqual(self.tokenizer.decode([256]), b"ab")

    def test_repr_reports_size(self):
        self.assertEqual(repr(self.tokenizer), "Tokenizer(size=256)")


if __name__ == "__main__":
    unittest.main()
