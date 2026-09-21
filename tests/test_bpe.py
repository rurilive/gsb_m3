"""BPE 训练与编码行为测试。"""

import os
import random
import subprocess
import sys
import tempfile
import time
import unittest

from bytetok import Tokenizer, Vocabulary, train_bpe
from bytetok.reference import naive_encode


class TestTrainBasics(unittest.TestCase):
    def test_appends_tokens_in_learn_order(self):
        vocab = Vocabulary()
        merges = train_bpe(b"ab ab ab ac", vocab, 257)
        self.assertEqual(merges, [(97, 98)])
        self.assertEqual(vocab.size(), 257)
        self.assertEqual(vocab.token(256), b"ab")

    def test_pair_counts_weighted_by_segment_frequency(self):
        vocab = Vocabulary()
        merges = train_bpe(b"aa aa aa ac", vocab, 258)
        self.assertEqual(merges[0], (97, 97))
        self.assertEqual(vocab.token(256), b"aa")

    def test_tie_break_is_byte_lexicographic(self):
        # ab 与 cd 频次都为 1：平票取两侧 token 字节字典序最小者
        vocab = Vocabulary()
        merges = train_bpe(b"ab cd", vocab, 258)
        self.assertEqual(merges, [(97, 98), (99, 100)])
        self.assertEqual(
            [vocab.token(256), vocab.token(257)],
            [b"ab", b"cd"],
        )

    def test_merges_never_cross_segments(self):
        vocab = Vocabulary()
        train_bpe(b"ab,ab,ab", vocab, 257)
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"ab,ab"), [256, ord(","), 256])

    def test_overlap_applied_left_to_right(self):
        vocab = Vocabulary()
        train_bpe(b"aaa aaa", vocab, 257)
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"aaa"), [256, 97])
        self.assertEqual(tokenizer.encode_bytes(b"baaa"), [98, 256, 97])

    def test_exhaustion_stops_before_target(self):
        vocab = Vocabulary()
        merges = train_bpe(b"ab", vocab, 1000)
        self.assertEqual(len(merges), 1)
        self.assertEqual(vocab.size(), 257)

    def test_validates_arguments(self):
        vocab = Vocabulary()
        with self.assertRaises(TypeError):
            train_bpe("ab", vocab, 300)
        with self.assertRaises(ValueError):
            train_bpe(b"ab", vocab, 100)


class TestEncode(unittest.TestCase):
    def test_no_merges_matches_naive_on_random_bytes(self):
        vocab = Vocabulary()
        tokenizer = Tokenizer(vocab)
        rng = random.Random(20260921)
        for _ in range(100):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 96)))
            self.assertEqual(tokenizer.encode_bytes(data), naive_encode(vocab, data))

    def test_uses_learned_merges_and_uncovered_falls_back_to_bytes(self):
        vocab = Vocabulary()
        train_bpe(b"ab ab ab", vocab, 257)
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"xab"), [120, 256])
        self.assertEqual(tokenizer.encode_bytes(b"xy"), [120, 121])
        self.assertEqual(tokenizer.decode(tokenizer.encode_bytes(b"xab")), b"xab")

    def test_repeated_merges_inside_one_word(self):
        vocab = Vocabulary()
        train_bpe(b"abab abab", vocab, 257)
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"abab"), [256, 256])


class TestDeterminism(unittest.TestCase):
    def test_same_corpus_same_params_gives_identical_result(self):
        corpus = self._corpus()
        vocab_a = Vocabulary()
        vocab_b = Vocabulary()
        merges_a = train_bpe(corpus, vocab_a, 1200)
        merges_b = train_bpe(corpus, vocab_b, 1200)
        self.assertEqual(merges_a, merges_b)
        self.assertEqual(vocab_a.tokens(), vocab_b.tokens())

    def test_independent_of_python_hash_seed(self):
        script = (
            "import random, sys;"
            "from bytetok import Vocabulary, train_bpe;"
            "rng = random.Random(555);"
            "words = [''.join(rng.choice('abcdefgh') for _ in range(rng.randrange(2,9))) for _ in range(400)];"
            "corpus = b' '.join(rng.choice(words).encode() for _ in range(2000));"
            "v = Vocabulary(); m = train_bpe(corpus, v, 900);"
            "print(len(m), m[:5], m[-5:])"
        )
        results = set()
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run(
                [sys.executable, "-c", script],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            results.add(out.stdout.strip())
        self.assertEqual(len(results), 1)

    @staticmethod
    def _corpus():
        rng = random.Random(808)
        words = [
            "".join(rng.choice("abcdefg") for _ in range(rng.randrange(2, 8)))
            for _ in range(300)
        ]
        return " ".join(rng.choice(words) for _ in range(1500)).encode("utf-8")


class TestReversibility(unittest.TestCase):
    def test_random_binary_roundtrip_after_training(self):
        train_rng = random.Random(11)
        corpus = bytes(train_rng.randrange(256) for _ in range(20000))
        vocab = Vocabulary()
        train_bpe(corpus, vocab, 700)
        tokenizer = Tokenizer(vocab)
        rng = random.Random(22)
        for _ in range(300):
            blob = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 200)))
            ids = tokenizer.encode_bytes(blob)
            self.assertEqual(tokenizer.decode(ids), blob)

    def test_multibyte_and_illegal_bytes_roundtrip(self):
        vocab = Vocabulary()
        train_bpe(("狐狸 跳过 狐狸".encode("utf-8") * 20), vocab, 300)
        tokenizer = Tokenizer(vocab)
        for blob in [
            "你好，世界🙂".encode("utf-8"),
            b"\xff\xfe\x80",
            b"e\xe4\xbd\xa0\xffo" + "好".encode("utf-8") + b"\x00\x80",
            b"",
        ]:
            self.assertEqual(tokenizer.decode(tokenizer.encode_bytes(blob)), blob)


class TestSpecials(unittest.TestCase):
    def test_special_kept_whole_and_restored(self):
        vocab = Vocabulary()
        vocab.add_special("<pad>")
        vocab.add_special("<p>")
        train_bpe(b"ab ab ab", vocab, vocab.size() + 1)
        tokenizer = Tokenizer(vocab)

        ids = tokenizer.encode_bytes(b"<pad>ab")
        self.assertEqual(ids, [256, 258])
        self.assertEqual(tokenizer.decode(ids), b"<pad>ab")

        ids = tokenizer.encode_bytes(b"<p>ab")
        self.assertEqual(ids[0], 257)
        self.assertEqual(tokenizer.decode(ids), b"<p>ab")

    def test_special_never_merged_even_if_rule_matches(self):
        vocab = Vocabulary()
        train_bpe(b"ab ab ab", vocab, 257)
        vocab.add_special(b"ab")
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"ab"), [vocab.token_id(b"ab")])
        self.assertEqual(tokenizer.decode([vocab.token_id(b"ab")]), b"ab")

    def test_special_accepts_str_and_rejects_empty(self):
        vocab = Vocabulary()
        token_id = vocab.add_special("<unk>")
        self.assertEqual(vocab.token(token_id), b"<unk>")
        self.assertTrue(vocab.is_special(b"<unk>"))
        with self.assertRaises(ValueError):
            vocab.add_special("")


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip_keeps_vocab_merges_and_encoding(self):
        rng = random.Random(303)
        words = [
            "".join(rng.choice("abcdefgh") for _ in range(rng.randrange(2, 9)))
            for _ in range(400)
        ]
        corpus = " ".join(rng.choice(words) for _ in range(2000)).encode("utf-8")

        vocab = Vocabulary()
        vocab.add_special("<pad>")
        train_bpe(corpus, vocab, 1500)
        tokenizer = Tokenizer(vocab)
        probe = b"<pad> " + " ".join(words[:50]).encode("utf-8") + b" \xff\x80"
        expected_ids = tokenizer.encode_bytes(probe)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "vocab.txt")
            vocab.save(path)
            loaded = Vocabulary.load(path)

        self.assertEqual(loaded.tokens(), vocab.tokens())
        self.assertEqual(loaded.merges(), vocab.merges())
        self.assertEqual(loaded.special_tokens(), vocab.special_tokens())
        self.assertEqual(Tokenizer(loaded).encode_bytes(probe), expected_ids)
        self.assertEqual(Tokenizer(loaded).decode(expected_ids), probe)


class TestPerformance(unittest.TestCase):
    def test_100k_bytes_to_4000_vocab_within_20s(self):
        rng = random.Random(2026)
        words = list({
            "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randrange(3, 10)))
            for _ in range(4000)
        })
        parts = []
        total = 0
        while total < 100_000:
            word = rng.choice(words).encode("utf-8")
            parts.append(word)
            total += len(word) + 1
        corpus = b" ".join(parts)[:100_000]

        vocab = Vocabulary()
        started = time.perf_counter()
        merges = train_bpe(corpus, vocab, 4000)
        elapsed = time.perf_counter() - started

        self.assertEqual(vocab.size(), 4000)
        self.assertEqual(len(merges), 4000 - 256)
        self.assertLess(elapsed, 20.0)


if __name__ == "__main__":
    unittest.main()
