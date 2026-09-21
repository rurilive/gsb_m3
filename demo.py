"""bytetok 现状演示。

第一段：切段，看空白与标点怎么把缓冲切开。
第二段：逐字节编码与解码，含多字节字符与随机二进制数据。
第三段：与朴素逐字节参考实现对拍。
第四段：段频次统计。
第五段：预留的合并学习演示位子（见文末注释）。
"""

import random

from bytetok import Tokenizer, Vocabulary
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

    # TODO(合并学习): train_bpe 落地后，在这里补三段演示：
    # 1) 拿一段语料训练到几千词表，打印合并条数与训练耗时
    # 2) 同一段文本训练前后 id 序列长度对比
    # 3) 学到的词表存盘再读回，编码结果与训练完的实例一致


if __name__ == "__main__":
    main()
