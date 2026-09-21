"""bytetok 现状演示。

第一段：切段，看空白与标点怎么把缓冲切开。
第二段：逐字节编码与解码，含多字节字符与随机二进制数据。
第三段：与朴素逐字节参考实现对拍。
第四段：段频次统计。
第五段：BPE 合并学习与词表存盘往返。
"""

import os
import random
import tempfile
import time

from bytetok import Tokenizer, Vocabulary, train_bpe
from bytetok.reference import naive_decode, naive_encode
from bytetok.units import segment_frequencies

SAMPLE = "The quick, brown 狐狸 跳过 3 只懒狗！a\tb"


def main():
    vocab = Vocabulary()
    tokenizer = Tokenizer(vocab)

    print("=== 切段 ===")
    data = SAMPLE.encode("utf-8")
    for segment in tokenizer.segments(SAMPLE):
        print(f"  {segment!r}")
    print(f"  词表大小 {vocab.size()}，id 与字节值一一对应")

    print()
    print("=== 编码与解码 ===")
    ids = tokenizer.encode(SAMPLE)
    print(f"  {len(SAMPLE)} 个字符，编码出 {len(ids)} 个 id")
    print(f"  前 16 个 id: {ids[:16]}")
    print(f"  解码与原文逐字节相等: {tokenizer.decode(ids) == data}")

    rng = random.Random(20260921)
    ok = 0
    for _ in range(50):
        blob = bytes(rng.randrange(0, 256) for _ in range(rng.randrange(0, 64)))
        if tokenizer.decode(tokenizer.encode_bytes(blob)) == blob:
            ok += 1
    print(f"  随机二进制样本 50 条，往返逐字节相等 {ok} 条")

    print()
    print("=== 与参考实现对拍 ===")
    print(f"  encode == naive_encode: {ids == naive_encode(vocab, data)}")
    print(f"  decode == naive_decode: {tokenizer.decode(ids) == naive_decode(vocab, ids)}")

    print()
    print("=== 高频段 ===")
    for segment, count in segment_frequencies(data)[:5]:
        print(f"  {segment!r} x {count}")

    print()
    print("=== BPE 合并学习 ===")
    train_rng = random.Random(2026)
    word_pool = [
        "".join(train_rng.choice("abcdefghijklmnop") for _ in range(train_rng.randrange(2, 8)))
        for _ in range(8000)
    ]
    sentences = [
        " ".join(train_rng.choice(word_pool) for _ in range(6))
        + train_rng.choice([".", ",", ";", "?", "!"])
        for _ in range(8000)
    ]
    corpus = " ".join(sentences).encode("utf-8")
    bpe_vocab = Vocabulary()
    bpe_vocab.add_special("<pad>")
    started = time.perf_counter()
    merges = train_bpe(corpus, bpe_vocab, 2800)
    elapsed = time.perf_counter() - started
    print(f"  语料 {len(corpus)} 字节，学到 {len(merges)} 条合并，词表 {bpe_vocab.size()}，耗时 {elapsed:.2f}s")

    bpe_tokenizer = Tokenizer(bpe_vocab)
    probe = "<pad> " + " ".join(word_pool[:20])
    probe_data = probe.encode("utf-8")
    before = naive_encode(bpe_vocab, probe_data)
    after = bpe_tokenizer.encode(probe)
    print(f"  同段文本：逐字节 {len(before)} 个 id -> BPE {len(after)} 个 id")
    print(f"  特殊标记 <pad> 整段保留：首个 id 为 {after[0]}，解码含 <pad>: {bpe_vocab.token(after[0]) == b'<pad>'}")
    print(f"  BPE 往返逐字节相等: {bpe_tokenizer.decode(after) == probe_data}")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vocab.txt")
        bpe_vocab.save(path)
        loaded = Vocabulary.load(path)
        loaded_tokenizer = Tokenizer(loaded)
        same = loaded_tokenizer.encode(probe) == after
        print(f"  save/load 后词表大小 {loaded.size()}、合并 {len(loaded.merges())} 条，编码一致: {same}")


if __name__ == "__main__":
    main()
