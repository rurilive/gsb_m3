"""字节级 BPE 训练。

训练口径（与编码严格一致，README 亦有简述）：

- 先用 ``units.split_segments`` 按空白/标点切段，统计每个**段**的频次，
  相邻字节对只在段内计数，永远不跨段合并。
- 每个段初始是一个字节 id 序列；所有段内对 (左 id, 右 id) 的频次
  按段频次加权汇总。
- 每轮选全局频次最高的对合并成新 token，新 token 追加进 Vocabulary，
  规则按学习顺序登记到词表。
- 平票取舍（写死，保证可复现）：先比频次；频次相同取
  ``(左 token 字节串, 右 token 字节串)`` 字典序最小的对。
- 同一轮内同一段的多处命中按位置从左到右处理，重叠命中（如
  ``a a a`` 上的两个 ``aa``）只合并最左一处。

性能上不做每轮全量重扫：段以链表保存，维护"对 -> 命中位置"倒排表，
每次合并只改受影响的三个邻接对；候选对放进懒删除堆，O(增量) 出胜者。
"""

import heapq

from bytetok.units import split_segments


class _Word:
    """一个段类型在训练中的链表形态。"""

    __slots__ = ("sym", "prev", "next", "freq")

    def __init__(self, sym, freq):
        self.sym = sym
        self.prev = [-1] + list(range(len(sym) - 1))
        self.next = list(range(1, len(sym))) + [-1]
        self.freq = freq


def _segment_counts(data):
    counts = {}
    for segment in split_segments(data):
        if len(segment) >= 2:
            counts[segment] = counts.get(segment, 0) + 1
    return counts


def train_bpe(data, vocab, target_size):
    """在 ``data``（bytes）上做 BPE 训练，原地扩充 ``vocab``。

    合并到词表大小达到 ``target_size`` 或没有可合并的对为止；
    返回词表中按学习顺序排列的全部合并规则
    ``[(左 id, 右 id), ...]``（即 ``vocab.merges()``）。

    同语料、同初始词表、同目标大小两次训练，词表与合并顺序逐项相同。
    """
    if not isinstance(data, bytes):
        raise TypeError("train_bpe 只接受 bytes，收到 %r" % (type(data).__name__,))
    if not isinstance(target_size, int) or isinstance(target_size, bool):
        raise TypeError("target_size 必须是 int，收到 %r" % (target_size,))
    if target_size < vocab.size():
        raise ValueError("target_size 不能小于当前词表大小")

    words = [
        _Word(list(segment), freq)
        for segment, freq in _segment_counts(data).items()
    ]

    pair_count = {}
    pair_nodes = {}
    pair_version = {}
    for word in words:
        sym = word.sym
        for pos in range(len(sym) - 1):
            pair = (sym[pos], sym[pos + 1])
            pair_count[pair] = pair_count.get(pair, 0) + word.freq
            pair_nodes.setdefault(pair, set()).add((word, pos))
            pair_version.setdefault(pair, 0)

    heap = []

    def push(pair):
        heapq.heappush(
            heap,
            (-pair_count[pair], pair[0], pair[1], pair_version[pair]),
        )

    for pair in pair_count:
        push(pair)

    def drop(pair, word, pos):
        pair_nodes[pair].discard((word, pos))
        count = pair_count.get(pair, 0) - word.freq
        if count <= 0:
            pair_count.pop(pair, None)
            pair_nodes.pop(pair, None)
            pair_version[pair] = pair_version.get(pair, 0) + 1
        else:
            pair_count[pair] = count
            pair_version[pair] = pair_version.get(pair, 0) + 1
            push(pair)

    def add(pair, word, pos):
        pair_count[pair] = pair_count.get(pair, 0) + word.freq
        pair_nodes.setdefault(pair, set()).add((word, pos))
        pair_version[pair] = pair_version.get(pair, 0) + 1
        push(pair)

    while vocab.size() < target_size and heap:
        neg_count, left_id, right_id, version = heapq.heappop(heap)
        pair = (left_id, right_id)
        if pair_count.get(pair, 0) != -neg_count or pair_version.get(pair, 0) != version:
            continue
        merged_bytes = vocab.token(left_id) + vocab.token(right_id)
        merged_id = vocab.token_id(merged_bytes) if merged_bytes in vocab else None

        buckets = {}
        for word, pos in pair_nodes.get(pair, ()):  # 快照，应用时再复验
            nxt = word.next[pos]
            if word.sym[pos] == left_id and nxt != -1 and word.sym[nxt] == right_id:
                buckets.setdefault(id(word), (word, []))[1].append(pos)

        for _key, (word, positions) in buckets.items():
            positions.sort()
            sym, prev, nxt = word.sym, word.prev, word.next
            for pos in positions:
                q = nxt[pos]
                if sym[pos] != left_id or q == -1 or sym[q] != right_id:
                    continue  # 本轮左侧的合并已让本位置失效（重叠命中）
                r = nxt[q]
                lp = prev[pos]

                pair_nodes[pair].discard((word, pos))
                pair_count[pair] -= word.freq

                if lp != -1:
                    drop((sym[lp], left_id), word, lp)
                if r != -1:
                    drop((right_id, sym[r]), word, q)

                if merged_id is None:
                    merged_id = vocab.register_merge(left_id, right_id)
                sym[pos] = merged_id
                nxt[pos] = r
                if r != -1:
                    prev[r] = pos
                nxt[q] = -1

                if lp != -1:
                    add((sym[lp], sym[pos]), word, lp)
                if r != -1:
                    add((sym[pos], sym[r]), word, pos)

        if pair_count.get(pair, 0) <= 0:
            pair_count.pop(pair, None)
            pair_nodes.pop(pair, None)
            pair_version[pair] = pair_version.get(pair, 0) + 1

    return vocab.merges()
