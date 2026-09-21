"""BPE 训练：统计相邻字节对频次，迭代合并到目标词表。

口径（由 tests/test_bpe.py 锁定，同语料同参数两次训练结果逐项相同）：

- 切段沿用 units.split_segments：合并只发生在段内，绝不跨段
  （段边界即 ASCII 空白/标点边界，多字节 UTF-8 字符不受影响）。
- 频次按“出现位置”计：同一个段在语料里出现 n 次，贡献 n 倍频次。
- 每轮选频次最高的相邻 id 对合并；平票按 (左 id, 右 id) 升序。
- 合并一个段内该对的全部非重叠出现，每次取最左侧；合并产物
  （左 token + 右 token）追加进 Vocabulary，拿到下一个 id。
- 合并产物已在词表中（如撞上特殊标记）时跳过该对，不占一轮。
- 频次表增量维护：只重算发生合并的段，绝不每轮全量重扫；
  候选对放进最小堆，失效条目惰性删除。
- 没有任何可合并的对（数据过短或目标已到顶）时提前结束。

返回的合并规则按学习顺序排列，元素为 (left_id, right_id)，可直接
交给 Tokenizer(vocab, merges)。
"""

import heapq

from bytetok.units import split_segments


def train_bpe(data, vocab, target_size):
    """在语料 data（bytes）上训练 BPE，直到 vocab.size() == target_size。

    合并产物追加进 vocab（原地修改），按学习顺序返回 (左id, 右id)
    规则列表。target_size 不大于当前词表时返回空列表；语料里没有
    足够多的不同对时，提前结束并返回实际学到的规则。
    """
    if not isinstance(data, bytes):
        raise TypeError("train_bpe 只接受 bytes，收到 %r" % (type(data).__name__,))
    if not isinstance(target_size, int) or isinstance(target_size, bool):
        raise TypeError("target_size 必须是 int")
    if target_size < vocab.size():
        raise ValueError(
            "target_size %d 小于当前词表大小 %d" % (target_size, vocab.size())
        )
    if target_size == vocab.size():
        return []

    # words：段符号序列（id 元组）-> 在语料里出现次数。
    words = {}
    for segment in split_segments(data):
        if len(segment) >= 2:
            symbols = tuple(segment)
            words[symbols] = words.get(symbols, 0) + 1

    # pair_counts：相邻对总频次（按位置计）；pair_words：持有该对的段集合，
    # 合并时只动这些段，不碰其他段。
    pair_counts = {}
    pair_words = {}
    for symbols, frequency in words.items():
        for index in range(len(symbols) - 1):
            pair = (symbols[index], symbols[index + 1])
            pair_counts[pair] = pair_counts.get(pair, 0) + frequency
            pair_words.setdefault(pair, set()).add(symbols)

    heap = [(-count, pair[0], pair[1]) for pair, count in pair_counts.items()]
    heapq.heapify(heap)
    merges = []

    while vocab.size() < target_size and heap:
        neg_count, left, right = heapq.heappop(heap)
        pair = (left, right)
        current = pair_counts.get(pair)
        if current is None or -neg_count != current:
            continue

        token = vocab.token(left) + vocab.token(right)
        if token in vocab:
            # 合并产物撞车（已登记的普通/特殊 token）：该对无法学习，
            # 原地删掉，不占一轮合并。
            pair_words.pop(pair, None)
            del pair_counts[pair]
            continue

        new_id = vocab.add(token)
        merges.append(pair)

        # 只重写真正持有该对的段；频次更新为局部差值，其余段原封不动。
        for old in list(pair_words[pair]):
            frequency = words.pop(old)
            rebuilt = []
            index = 0
            while index < len(old):
                if (
                    index < len(old) - 1
                    and old[index] == left
                    and old[index + 1] == right
                ):
                    rebuilt.append(new_id)
                    index += 2
                else:
                    rebuilt.append(old[index])
                    index += 1
            rebuilt = tuple(rebuilt)

            local_old = {}
            for index in range(len(old) - 1):
                entry = (old[index], old[index + 1])
                local_old[entry] = local_old.get(entry, 0) + 1
            local_new = {}
            for index in range(len(rebuilt) - 1):
                entry = (rebuilt[index], rebuilt[index + 1])
                local_new[entry] = local_new.get(entry, 0) + 1

            for entry, amount in local_old.items():
                if entry not in pair_counts:
                    continue
                count = pair_counts[entry] - amount * frequency
                holders = pair_words[entry]
                holders.discard(old)
                if count <= 0:
                    del pair_counts[entry]
                    if not holders:
                        del pair_words[entry]
                else:
                    pair_counts[entry] = count
                    heapq.heappush(heap, (-count, entry[0], entry[1]))
            for entry, amount in local_new.items():
                count = pair_counts.get(entry, 0) + amount * frequency
                pair_counts[entry] = count
                pair_words.setdefault(entry, set()).add(rebuilt)
                heapq.heappush(heap, (-count, entry[0], entry[1]))

            words[rebuilt] = words.get(rebuilt, 0) + frequency

    return merges
