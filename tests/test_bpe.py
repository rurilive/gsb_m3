"""真 BPE 行为锁定测试。

锁定项：
- train_bpe 的合并顺序与词表追加，和“每轮全量重扫”的朴素实现一致；
  平票取舍写死为 (左 id, 右 id) 升序；
- 同语料同参数两次训练，规则与词表逐项相同；
- Tokenizer 走合并，未覆盖字节退回逐字节；无合并时与 naive_encode
  逐项一致；任意二进制往返逐字节还原；
- add_special 标记编码整段保留、解码原样还原；
- Vocabulary save/load 往返（含特殊标记）一致；
- 十万字节训到四千词表在 20 秒内完成。
"""

import os
import random
import tempfile
import time
import unittest

from bytetok import Tokenizer, Vocabulary, train_bpe
from bytetok.reference import naive_encode
from bytetok.units import is_separator, split_segments


def oracle_train(data, target_size):
    """每轮全量重扫的朴素 BPE，作 train_bpe 的对拍基准。

    平票按 (左 id, 右 id) 升序，段内每次合并最左侧出现。
    """
    vocab = Vocabulary()
    words = {}
    for segment in split_segments(data):
        if len(segment) >= 2:
            symbols = tuple(segment)
            words[symbols] = words.get(symbols, 0) + 1
    merges = []
    while vocab.size() < target_size:
        counts = {}
        for symbols, frequency in words.items():
            for index in range(len(symbols) - 1):
                pair = (symbols[index], symbols[index + 1])
                counts[pair] = counts.get(pair, 0) + frequency
        if not counts:
            break
        top = max(counts.values())
        pair = min(item for item, count in counts.items() if count == top)
        new_id = vocab.add(vocab.token(pair[0]) + vocab.token(pair[1]))
        merges.append(pair)
        rebuilt_words = {}
        for symbols, frequency in words.items():
            rebuilt = []
            index = 0
            while index < len(symbols):
                if (
                    index < len(symbols) - 1
                    and symbols[index] == pair[0]
                    and symbols[index + 1] == pair[1]
                ):
                    rebuilt.append(new_id)
                    index += 2
                else:
                    rebuilt.append(symbols[index])
                    index += 1
            key = tuple(rebuilt)
            rebuilt_words[key] = rebuilt_words.get(key, 0) + frequency
        words = rebuilt_words
    return merges, vocab.tokens()


def make_corpus(seed, size, alphabet):
    rng = random.Random(seed)
    parts = []
    total = 0
    while total < size:
        part = bytes(rng.choice(alphabet) for _ in range(rng.randrange(3, 9)))
        parts.append(part)
        parts.append(b" ")
        total += len(part) + 1
    return b"".join(parts)[:size]


class TestTrainBasics(unittest.TestCase):
    def test_target_equal_returns_empty_and_leaves_vocab(self):
        vocab = Vocabulary()
        self.assertEqual(train_bpe(b"abc abc", vocab, 256), [])
        self.assertEqual(vocab.size(), 256)

    def test_target_below_current_raises(self):
        vocab = Vocabulary()
        vocab.add(b"ab")
        with self.assertRaises(ValueError):
            train_bpe(b"ab ab", vocab, 256)

    def test_rejects_non_bytes_and_non_int_target(self):
        vocab = Vocabulary()
        with self.assertRaises(TypeError):
            train_bpe("abc", vocab, 300)
        with self.assertRaises(TypeError):
            train_bpe(b"abc", vocab, 300.0)

    def test_empty_and_single_byte_segments_learn_nothing(self):
        vocab = Vocabulary()
        self.assertEqual(train_bpe(b"", vocab, 400), [])
        self.assertEqual(vocab.size(), 256)
        vocab = Vocabulary()
        self.assertEqual(train_bpe(b"a,b!c?", vocab, 400), [])
        self.assertEqual(vocab.size(), 256)

    def test_merges_append_tokens_in_learning_order(self):
        vocab = Vocabulary()
        merges = train_bpe(b"ab ab ab ac", vocab, 260)
        self.assertEqual(merges[0], (97, 98))
        self.assertEqual(vocab.token(256), b"ab")
        self.assertEqual(vocab.token_id(b"ab"), 256)

    def test_exhausted_data_stops_before_target(self):
        vocab = Vocabulary()
        merges = train_bpe(b"ab cd", vocab, 400)
        self.assertLess(vocab.size(), 400)
        self.assertEqual(len(merges), vocab.size() - 256)


class TestTrainDeterminism(unittest.TestCase):
    def test_same_data_same_params_twice_identical(self):
        data = make_corpus(7, 20_000, bytes(range(0x80, 0x100)) + b"abcdefg ")
        first_vocab = Vocabulary()
        first_merges = train_bpe(data, first_vocab, 600)
        second_vocab = Vocabulary()
        second_merges = train_bpe(data, second_vocab, 600)
        self.assertEqual(first_merges, second_merges)
        self.assertEqual(first_vocab.tokens(), second_vocab.tokens())

    def test_tie_break_is_ascending_pair_ids(self):
        # ab 与 cd 各出现一次，严格平票：先合并 id 对更小的 (97,98)。
        vocab = Vocabulary()
        merges = train_bpe(b"ab cd", vocab, 257)
        self.assertEqual(merges, [(97, 98)])
        self.assertEqual(vocab.token(256), b"ab")

        # 左侧同为 x 时按右 id 升序：xa(120,97) 在 xb(120,98) 前。
        vocab = Vocabulary()
        merges = train_bpe(b"xa xb", vocab, 258)
        self.assertEqual(merges[0], (120, 97))


class TestTrainMatchesOracle(unittest.TestCase):
    def test_matches_full_rescan_oracle_on_mixed_corpora(self):
        rng = random.Random(20260921)
        corpora = [
            b"a a a b b ab ab ba low lower widest newest",
            bytes(rng.choice(b"abcdefgh ") for _ in range(3000)),
            bytes(rng.randrange(256) for _ in range(3000)),
            "你好世界 狐狸跳过懒狗，世界和平！狐狸 狐狸 世界 ".encode() * 10,
            make_corpus(11, 20_000, b"etaoinshrdlu "),
            make_corpus(13, 10_000, bytes(range(256))),
        ]
        for corpus in corpora:
            expected_merges, expected_tokens = oracle_train(corpus, 400)
            vocab = Vocabulary()
            merges = train_bpe(corpus, vocab, 400)
            self.assertEqual(merges, expected_merges)
            self.assertEqual(vocab.tokens(), expected_tokens)

    def test_merges_never_cross_segment_boundaries(self):
        vocab = Vocabulary()
        train_bpe(b"a,b!c? a,b!c?", vocab, 300)
        for token_id in range(256, vocab.size()):
            token = vocab.token(token_id)
            flags = [is_separator(value) for value in token]
            self.assertTrue(
                all(flags) or not any(flags),
                "合并 token 跨越了分隔/词段边界: %r" % (token,),
            )


class TestTokenizerBpe(unittest.TestCase):
    def setUp(self):
        self.data = b"the quick brown fox the quick fox"
        self.vocab = Vocabulary()
        self.merges = train_bpe(self.data, self.vocab, 300)
        self.tokenizer = Tokenizer(self.vocab, self.merges)

    def test_no_merges_matches_naive_encode(self):
        vocab = Vocabulary()
        tokenizer = Tokenizer(vocab)
        samples = [
            b"",
            b"abc",
            "你好，世界！🙂".encode("utf-8"),
            bytes(range(256)),
            b"mixed " + "混合".encode("utf-8") + b" \xff\xfe\x80 bytes",
        ]
        rng = random.Random(99)
        samples.extend(
            bytes(rng.randrange(256) for _ in range(rng.randrange(0, 128)))
            for _ in range(100)
        )
        for sample in samples:
            self.assertEqual(
                tokenizer.encode_bytes(sample),
                naive_encode(vocab, sample),
            )

    def test_bpe_is_shorter_and_roundtrips(self):
        ids = self.tokenizer.encode_bytes(self.data)
        self.assertLess(len(ids), len(self.data))
        self.assertEqual(self.tokenizer.decode(ids), self.data)

    def test_encode_uses_learned_ids(self):
        ids = self.tokenizer.encode_bytes(b"the the the")
        self.assertTrue(any(token_id >= 256 for token_id in ids))
        self.assertEqual(self.tokenizer.decode(ids), b"the the the")

    def test_uncovered_bytes_fall_back(self):
        vocab = Vocabulary()
        merges = train_bpe(b"aaaa", vocab, 257)
        self.assertEqual(merges, [(97, 97)])
        tokenizer = Tokenizer(vocab, merges)
        self.assertEqual(tokenizer.encode_bytes(b"zaaa!b"), [122, 256, 97, 33, 98])

    def test_merges_do_not_cross_segments(self):
        vocab = Vocabulary()
        merges = train_bpe(b"ab ab", vocab, 257)
        tokenizer = Tokenizer(vocab, merges)
        self.assertEqual(tokenizer.encode_bytes(b"ab ab"), [256, 32, 256])

    def test_str_encode_goes_through_utf8(self):
        ids = self.tokenizer.encode("the quick 狐狸")
        self.assertEqual(
            self.tokenizer.decode(ids),
            "the quick 狐狸".encode("utf-8"),
        )


class TestRoundtripRandom(unittest.TestCase):
    def test_random_binary_roundtrip_after_training(self):
        train_corpus = bytes(random.Random(1).randrange(256) for _ in range(20_000))
        vocab = Vocabulary()
        merges = train_bpe(train_corpus, vocab, 600)
        tokenizer = Tokenizer(vocab, merges)
        rng = random.Random(20260921)
        for _ in range(500):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 256)))
            ids = tokenizer.encode_bytes(data)
            self.assertEqual(tokenizer.decode(ids), data)

    def test_multibyte_and_invalid_bytes_roundtrip(self):
        train_corpus = (
            "你好世界，狐狸！🙂🙃 ".encode("utf-8") * 200
            + bytes(range(0x80, 0x100)) * 20
        )
        vocab = Vocabulary()
        merges = train_bpe(train_corpus, vocab, 500)
        tokenizer = Tokenizer(vocab, merges)
        samples = [
            "你好，世界".encode("utf-8"),
            "🙂🙃 mixed 混合".encode("utf-8"),
            b"\xff\xfe\x80\xc0\xaf",
            bytes(range(256)),
            b"end \xe4\xbd start",
        ]
        for data in samples:
            ids = tokenizer.encode_bytes(data)
            self.assertEqual(tokenizer.decode(ids), data)


class TestSpecialTokens(unittest.TestCase):
    def test_add_special_registers_in_order(self):
        vocab = Vocabulary()
        first = vocab.add_special("<|endoftext|>")
        second = vocab.add_special("<|pad|>")
        self.assertEqual(first, 256)
        self.assertEqual(second, 257)
        self.assertEqual(vocab.special_tokens(), [b"<|endoftext|>", b"<|pad|>"])
        self.assertEqual(vocab.special_ids(), [256, 257])
        self.assertTrue(vocab.is_special(first))
        self.assertFalse(vocab.is_special(97))

    def test_add_special_accepts_str_and_is_idempotent(self):
        vocab = Vocabulary()
        self.assertEqual(
            vocab.add_special("<|endoftext|>"),
            vocab.add_special("<|endoftext|>"),
        )
        self.assertEqual(vocab.special_tokens(), [b"<|endoftext|>"])

    def test_special_token_kept_whole_in_encode(self):
        vocab = Vocabulary()
        end_id = vocab.add_special("<|endoftext|>")
        merges = train_bpe(b"hello hello world world", vocab, 280)
        tokenizer = Tokenizer(vocab, merges)
        data = b"hello<|endoftext|>world"
        ids = tokenizer.encode_bytes(data)
        self.assertEqual(ids.count(end_id), 1)
        self.assertEqual(tokenizer.decode(ids), data)

    def test_special_with_separator_bytes_kept_whole(self):
        vocab = Vocabulary()
        mark_id = vocab.add_special("</s>")
        tokenizer = Tokenizer(vocab)
        data = b"a</s>b"
        self.assertEqual(tokenizer.encode_bytes(data), [97, mark_id, 98])
        self.assertEqual(tokenizer.decode(tokenizer.encode_bytes(data)), data)

    def test_longest_special_wins(self):
        vocab = Vocabulary()
        vocab.add_special("a")
        longer = vocab.add_special("ab")
        tokenizer = Tokenizer(vocab)
        self.assertEqual(tokenizer.encode_bytes(b"ab"), [longer])

    def test_multiple_specials_roundtrip(self):
        vocab = Vocabulary()
        begin = vocab.add_special("<s>")
        end = vocab.add_special("</s>")
        tokenizer = Tokenizer(vocab)
        data = b"<s>hello</s>"
        ids = tokenizer.encode_bytes(data)
        self.assertEqual(ids[0], begin)
        self.assertEqual(ids[-1], end)
        self.assertEqual(tokenizer.decode(ids), data)

    def test_special_collision_pair_is_skipped_in_training(self):
        vocab = Vocabulary()
        special_id = vocab.add_special(b"ab")
        merges = train_bpe(b"ab ab cd cd", vocab, 260)
        # 对 (97,98) 的合并产物撞上特殊标记，跳过；先学到 (99,100)。
        self.assertEqual(merges[0], (99, 100))
        self.assertEqual(vocab.token(special_id), b"ab")
        tokenizer = Tokenizer(vocab, merges)
        data = b"ab cd"
        ids = tokenizer.encode_bytes(data)
        self.assertEqual(tokenizer.decode(ids), data)
        self.assertIn(special_id, ids)

    def test_random_roundtrip_with_specials(self):
        vocab = Vocabulary()
        vocab.add_special("<s>")
        vocab.add_special("</s>")
        merges = train_bpe(b"alpha beta gamma alpha beta gamma", vocab, 280)
        tokenizer = Tokenizer(vocab, merges)
        rng = random.Random(31337)
        alphabet = b"abcdefgh </s>"
        for _ in range(200):
            pieces = []
            for _ in range(rng.randrange(0, 6)):
                if rng.random() < 0.3:
                    pieces.append(rng.choice([b"<s>", b"</s>"]))
                else:
                    pieces.append(bytes(rng.choice(alphabet) for _ in range(rng.randrange(0, 8))))
            data = b"".join(pieces)
            ids = tokenizer.encode_bytes(data)
            self.assertEqual(tokenizer.decode(ids), data)


class TestVocabularySaveLoad(unittest.TestCase):
    def _trained(self):
        vocab = Vocabulary()
        vocab.add_special("<|endoftext|>")
        merges = train_bpe(b"hello world hello world fox fox", vocab, 280)
        return vocab, merges

    def test_roundtrip_file_path(self):
        vocab, merges = self._trained()
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            vocab.save(path)
            loaded = Vocabulary.load(path)
        finally:
            os.unlink(path)
        self.assertEqual(loaded.tokens(), vocab.tokens())
        self.assertEqual(loaded.special_tokens(), vocab.special_tokens())
        self.assertEqual(loaded.special_ids(), vocab.special_ids())
        tokenizer = Tokenizer(loaded, merges)
        data = b"<|endoftext|>hello world fox"
        self.assertEqual(
            tokenizer.encode_bytes(data),
            Tokenizer(vocab, merges).encode_bytes(data),
        )
        self.assertEqual(tokenizer.decode(tokenizer.encode_bytes(data)), data)

    def test_roundtrip_file_object(self):
        vocab, _ = self._trained()
        import io

        buffer = io.BytesIO()
        vocab.save(buffer)
        buffer.seek(0)
        loaded = Vocabulary.load(buffer)
        self.assertEqual(loaded.tokens(), vocab.tokens())
        self.assertEqual(loaded.special_tokens(), vocab.special_tokens())

    def test_plain_vocab_roundtrip_without_special(self):
        vocab = Vocabulary()
        train_bpe(b"ab ab cd cd", vocab, 260)
        import io

        buffer = io.BytesIO()
        vocab.save(buffer)
        buffer.seek(0)
        loaded = Vocabulary.load(buffer)
        self.assertEqual(loaded.tokens(), vocab.tokens())
        self.assertEqual(loaded.special_tokens(), [])

    def test_load_rejects_bad_file(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            with open(path, "wb") as handle:
                handle.write(b"not a vocab file at all")
            with self.assertRaises(ValueError):
                Vocabulary.load(path)
        finally:
            os.unlink(path)


class TestPerformance(unittest.TestCase):
    def test_100k_bytes_to_4000_vocab_under_20_seconds(self):
        corpus = make_corpus(20260921, 100_000, bytes(range(97, 123)) + b" ")
        self.assertEqual(len(corpus), 100_000)
        vocab = Vocabulary()
        started = time.perf_counter()
        merges = train_bpe(corpus, vocab, 4000)
        elapsed = time.perf_counter() - started
        self.assertEqual(vocab.size(), 4000)
        self.assertEqual(len(merges), 4000 - 256)
        self.assertLess(elapsed, 20.0)

        # 训练结果立刻可用且可逆。
        tokenizer = Tokenizer(vocab, merges)
        ids = tokenizer.encode_bytes(corpus)
        self.assertEqual(tokenizer.decode(ids), corpus)
        self.assertLess(len(ids), len(corpus))


if __name__ == "__main__":
    unittest.main()
