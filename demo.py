"""bytetok 现状演示。

第一段：切段，看空白与标点怎么把缓冲切开。
第二段：逐字节编码与解码，含多字节字符与随机二进制数据。
第三段：与朴素逐字节参考实现对拍。
第四段：段频次统计。
第五段：BPE 训练、合并前后长度对比、词表存盘往返。
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
    print("=== BPE 训练 ===")
    rng = random.Random(20260921)
    words = [
        bytes(rng.randrange(97, 123) for _ in range(rng.randrange(3, 9)))
        for _ in range(4000)
    ]
    parts = []
    while sum(len(part) for part in parts) < 100_000:
        parts.append(words[rng.randrange(len(words))])
        parts.append(b" ")
    corpus = b"".join(parts)[:100_000]

    bpe_vocab = Vocabulary()
    started = time.perf_counter()
    merges = train_bpe(corpus, bpe_vocab, 4000)
    elapsed = time.perf_counter() - started
    print(f"  语料 {len(corpus)} 字节，学到 {len(merges)} 条合并，耗时 {elapsed:.2f}s")
    print(f"  词表 {bpe_vocab.size()}，前 5 条规则: {merges[:5]}")

    print()
    print("=== 合并前后长度对比 ===")
    naive_vocab = Vocabulary()
    probe = corpus[:2000]
    before = naive_encode(naive_vocab, probe)
    bpe_tokenizer = Tokenizer(bpe_vocab, merges)
    after = bpe_tokenizer.encode_bytes(probe)
    print(f"  同一段 {len(probe)} 字节：逐字节 {len(before)} 个 id，BPE {len(after)} 个 id")
    print(f"  压缩到 {len(after) / len(before):.1%}，解码逐字节还原: {bpe_tokenizer.decode(after) == probe}")

    print()
    print("=== 词表存盘往返 ===")
    bpe_vocab.add_special("<|endoftext|>")
    fd, path = tempfile.mkstemp(prefix="bytetok-", suffix=".vocab")
    os.close(fd)
    try:
        bpe_vocab.save(path)
        reloaded = Vocabulary.load(path)
        reloaded_tokenizer = Tokenizer(reloaded, merges)
        sample = b"<|endoftext|>" + probe[:64]
        same = reloaded_tokenizer.encode_bytes(sample) == bpe_tokenizer.encode_bytes(sample)
        print(f"  存盘 {os.path.getsize(path)} 字节，读回后编码一致: {same}")
        print(f"  特殊标记保留: {reloaded.special_tokens() == bpe_vocab.special_tokens()}")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    main()
