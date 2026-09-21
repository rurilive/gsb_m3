"""分词器：切段后按学到的合并规则做 BPE，解码按 id 取字节串拼回。

没有合并规则（merges 为空）时，encode_bytes 与
reference.naive_encode 结果逐项一致。特殊标记（vocab.add_special
登记）在编码时整段匹配保留，不参与切段与合并，解码原样还原。
"""

from bytetok.reference import naive_decode
from bytetok.units import split_segments


class Tokenizer:
    """把文本或字节串编码成 id 序列，并能原样解码回字节串。"""

    def __init__(self, vocab, merges=()):
        """merges 为按学习顺序排列的 (左id, 右id) 规则，可由
        train_bpe 的返回值直接传入；缺省即纯逐字节模式。
        """
        self.vocab = vocab
        self.merges = list(merges)
        self._ranks = {pair: rank for rank, pair in enumerate(self.merges)}
        self._merge_id = {
            pair: vocab.token_id(vocab.token(pair[0]) + vocab.token(pair[1]))
            for pair in self.merges
        }

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
        """字节串编码：特殊标记整段保留，其余逐段走合并。

        同一位置有多个标记可匹配时取更长的；长度相同取先登记的。
        没有覆盖到的字节退回逐字节 id，因此 merges 为空时与
        reference.naive_encode 逐项一致。
        """
        if not isinstance(data, bytes):
            raise TypeError("encode_bytes 只接受 bytes，收到 %r" % (type(data).__name__,))
        ids = []
        specials = self.vocab.special_tokens()
        index = 0
        while index < len(data):
            match = None
            if specials:
                for token in specials:
                    if (
                        data.startswith(token, index)
                        and (
                            match is None
                            or len(token) > len(match)
                        )
                    ):
                        match = token
            if match is not None:
                ids.append(self.vocab.token_id(match))
                index += len(match)
                continue
            next_cut = len(data)
            for token in specials:
                cut = data.find(token, index + 1)
                if cut != -1 and cut < next_cut:
                    next_cut = cut
            chunk = data[index:next_cut]
            index = next_cut
            for segment in split_segments(chunk):
                if len(segment) == 1:
                    ids.append(segment[0])
                else:
                    ids.extend(self._bpe_segment(segment))
        return ids

    def _bpe_segment(self, segment):
        """段内反复合并：每轮取学习序号最小的相邻对（平票取最左），
        合并它，直到没有规则可应用；没覆盖的符号逐字节保留。
        """
        symbols = list(segment)
        while len(symbols) >= 2:
            best_rank = None
            best_index = -1
            for index in range(len(symbols) - 1):
                rank = self._ranks.get((symbols[index], symbols[index + 1]))
                if rank is not None and (best_rank is None or rank < best_rank):
                    best_rank = rank
                    best_index = index
            if best_rank is None:
                break
            symbols[best_index:best_index + 2] = [
                self._merge_id[(symbols[best_index], symbols[best_index + 1])]
            ]
        return symbols

    def decode(self, ids):
        """id 序列解码回字节串；未知 id 抛 KeyError。"""
        return naive_decode(self.vocab, ids)

    def __repr__(self):
        return "Tokenizer(size=%d)" % (self.vocab.size(),)
