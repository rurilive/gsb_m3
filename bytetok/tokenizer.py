"""分词器：先切段，再把每个字节映射成词表里的 id。

当前版本词表固定，encode 与 reference.naive_encode 结果一致。
"""

from bytetok.reference import naive_decode
from bytetok.units import split_segments


class Tokenizer:
    """把文本或字节串编码成 id 序列，并能原样解码回字节串。"""

    def __init__(self, vocab):
        self.vocab = vocab

    def segments(self, text):
        """展示切段结果：str 先转 UTF-8 字节再切。"""
        if not isinstance(text, str):
            raise TypeError("segments 只接受 str，收到 %r" % (type(text).__name__,))
        return split_segments(text.encode("utf-8"))

    def encode(self, text):
        """str 编码：先转 UTF-8 字节，再走 encode_bytes。"""
        if not isinstance(text, str):
            raise TypeError("encode 只接受 str，收到 %r" % (type(text).__name__,))
        return self.encode_bytes(text.encode("utf-8"))

    def encode_bytes(self, data):
        """字节串编码：逐段、逐字节取 id。"""
        if not isinstance(data, bytes):
            raise TypeError("encode_bytes 只接受 bytes，收到 %r" % (type(data).__name__,))
        ids = []
        for segment in split_segments(data):
            for value in segment:
                ids.append(self.vocab.token_id(bytes([value])))
        return ids

    def decode(self, ids):
        """id 序列解码回字节串；未知 id 抛 KeyError。"""
        return naive_decode(self.vocab, ids)

    def __repr__(self):
        return "Tokenizer(size=%d)" % (self.vocab.size(),)
