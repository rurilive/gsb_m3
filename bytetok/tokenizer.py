"""分词器：先切段，再在段内按词表的合并规则做 BPE。

编码口径：

- 特殊标记（``vocab.add_special`` 登记）在字节流里按"最长优先、
  同长按标记字节升序"整段匹配，输出其 id，不参与合并。
- 其余字节先 ``split_segments`` 切段，对每个段套用 ``vocab.merges()``：
  从最低优先级（最早学到）的规则开始反复合并，与训练时的左到右
  应用方式一致；没有任何规则时就是逐字节编码。
- 合并不跨段，没被规则覆盖的字节退回逐字节 id，任何 bytes 输入
  （含非法 UTF-8）都可逆。
"""

import heapq

from bytetok.reference import naive_decode
from bytetok.units import split_segments


class Tokenizer:
    """把文本或字节串编码成 id 序列，并能原样解码回字节串。"""

    def __init__(self, vocab):
        self.vocab = vocab

    def _merge_rank(self):
        """(左 id, 右 id) -> 优先级；0 为最早学到、最优先。"""
        return {pair: rank for rank, pair in enumerate(self.vocab.merges())}

    def _special_table(self):
        """首字节 -> [(长度, token 字节, id)]，长在前、同长按字节升序。"""
        table = {}
        for token in self.vocab.special_tokens():
            table.setdefault(token[0], []).append(token)
        for token_list in table.values():
            token_list.sort(key=lambda token: (-len(token), token))
        return {
            first: [(len(token), token, self.vocab.token_id(token)) for token in token_list]
            for first, token_list in table.items()
        }

    def _apply_merges(self, segment, rank):
        """对一个段做 BPE 合并，与训练的左到右同时应用语义一致。"""
        ids = list(segment)
        if not rank or len(ids) < 2:
            return ids

        prev_link = [-1] + list(range(len(ids) - 1))
        next_link = list(range(1, len(ids))) + [-1]
        heap = []

        def push(pos):
            nxt = next_link[pos]
            if nxt != -1:
                pair = (ids[pos], ids[nxt])
                pair_rank = rank.get(pair)
                if pair_rank is not None:
                    heapq.heappush(heap, (pair_rank, pos))

        for pos in range(len(ids) - 1):
            push(pos)

        while heap:
            pair_rank, pos = heapq.heappop(heap)
            nxt = next_link[pos]
            if nxt == -1 or rank.get((ids[pos], ids[nxt])) != pair_rank:
                continue
            merged = self.vocab.token(ids[pos]) + self.vocab.token(ids[nxt])
            ids[pos] = self.vocab.token_id(merged)
            right = nxt
            nxt_of_right = next_link[right]
            next_link[pos] = nxt_of_right
            if nxt_of_right != -1:
                prev_link[nxt_of_right] = pos
            next_link[right] = -1
            left_pos = prev_link[pos]
            if left_pos != -1:
                push(left_pos)
            push(pos)

        result = []
        pos = 0
        while pos != -1:
            result.append(ids[pos])
            pos = next_link[pos]
        return result

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
        """字节串编码：特殊标记整段保留，其余切段后套用 BPE 合并。"""
        if not isinstance(data, bytes):
            raise TypeError("encode_bytes 只接受 bytes，收到 %r" % (type(data).__name__,))
        rank = self._merge_rank()
        specials = self._special_table()
        ids = []
        cursor = 0
        total = len(data)
        while cursor < total:
            candidates = specials.get(data[cursor])
            special_id = None
            special_len = 0
            if candidates:
                for length, token, token_id in candidates:
                    if data[cursor:cursor + length] == token:
                        special_id, special_len = token_id, length
                        break
            if special_id is not None:
                ids.append(special_id)
                cursor += special_len
                continue
            end = cursor + 1
            while end < total and data[end] not in specials:
                end += 1
            chunk = data[cursor:end]
            for segment in split_segments(chunk):
                ids.extend(self._apply_merges(segment, rank))
            cursor = end
        return ids

    def decode(self, ids):
        """id 序列解码回字节串；未知 id 抛 KeyError。"""
        return naive_decode(self.vocab, ids)

    def __repr__(self):
        return "Tokenizer(size=%d)" % (self.vocab.size(),)
