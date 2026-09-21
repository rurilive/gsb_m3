"""BM25 相关度索引。

与 :class:`~docbase.library.DocLibrary` 挂接：构造时收一遍现有文档，
之后靠 subscribe 回调跟随库的增、删、覆盖，单篇维护开销只跟该篇
词项数有关，不随库规模涨。

打分口径是标准 BM25（Lucene 式 IDF）：

    idf(t) = ln((N - df + 0.5) / (df + 0.5) + 1)
    score  = Σ_t idf(t) * f(t, d) * (k1 + 1)
             / (f(t, d) + k1 * (1 - b + b * |d| / avgdl))

检索时用 WAND（weak AND）跳过不可能进前 k 的文档，只给少量候选
做完整打分，``stats()`` 里的 ``scored`` 记录累计完整打分次数。
"""

import heapq
import math
from collections import Counter

from .text import _WORD_RE, chunks

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def rank_tokens(text):
    """排序用的切词口径。

    中文段取相邻二字组（非重叠，0-2、2-4……），末尾只剩一个字也
    保留；英文数字段按 tokens 的口径切段并转小写。查询词靠去重
    兜底，这里不做去重。
    """
    words = []
    for kind, segment in chunks(text.casefold()):
        if kind == "cjk":
            pos = 0
            length = len(segment)
            while pos + 2 <= length:
                words.append(segment[pos:pos + 2])
                pos += 2
            if pos < length:
                words.append(segment[pos])
        else:
            words.extend(_WORD_RE.findall(segment))
    return words


def _dedup(words):
    """按首次出现顺序去重。"""
    return list(dict.fromkeys(words))


class _RevStr(str):
    """反字典序的 doc_id：相等分比 id，id 小的应当排在堆顶。"""

    def __lt__(self, other):
        return str.__gt__(self, other)

    def __le__(self, other):
        return str.__ge__(self, other)

    def __gt__(self, other):
        return str.__lt__(self, other)

    def __ge__(self, other):
        return str.__le__(self, other)


class BM25Index:
    """跟随 DocLibrary 的 BM25 倒排索引。"""

    def __init__(self, library, k1=DEFAULT_K1, b=DEFAULT_B):
        self._lib = library
        self.k1 = k1
        self.b = b
        # term -> {doc_id: tf}
        self._postings = {}
        # doc_id -> set(term)，删除覆盖时精确回滚
        self._doc_terms = {}
        self._doc_len = {}
        self._total_len = 0
        self._scored = 0
        for doc_id, text in library.scan():
            self._add_doc(doc_id, text)
        library.subscribe(self._on_change)

    # ---- 增量维护 -------------------------------------------------

    def _on_change(self, doc_id, old, new):
        if old is not None:
            self._remove_doc(doc_id)
        if new is not None:
            self._add_doc(doc_id, new)

    def _add_doc(self, doc_id, text):
        terms = Counter(rank_tokens(text))
        self._doc_len[doc_id] = sum(terms.values())
        self._total_len += self._doc_len[doc_id]
        self._doc_terms[doc_id] = set(terms)
        for term, freq in terms.items():
            self._postings.setdefault(term, {})[doc_id] = freq

    def _remove_doc(self, doc_id):
        for term in self._doc_terms.pop(doc_id):
            posting = self._postings[term]
            del posting[doc_id]
            if not posting:
                del self._postings[term]
        self._total_len -= self._doc_len.pop(doc_id)

    # ---- 检索 -----------------------------------------------------

    def search(self, query, k):
        """返回前 k 条 ``(doc_id, score)``。

        分高在前，同分按 doc_id 字典序；查询词去重后各算一次，
        分非正（词项不在库中或无词项）的文档不返回。
        """
        if k <= 0:
            return []
        terms = _dedup(rank_tokens(query))
        n = len(self._doc_len)
        if not terms or n == 0:
            return []
        avgdl = self._total_len / n

        # 每个词项的 idf 与排序后的倒排链；不在库中的词项直接丢掉。
        entries = []
        for term in terms:
            posting = self._postings.get(term)
            if not posting:
                continue
            df = len(posting)
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            ids = sorted(posting)
            entries.append(
                {
                    "term": term,
                    "idf": idf,
                    "ids": ids,
                    "posting": posting,
                    "cursor": 0,
                    "ub": idf * (self.k1 + 1.0),
                }
            )
        if not entries:
            return []

        # 堆里放 (score, _RevStr(doc_id))：分高在前，同分 id 小在前。
        heap = []
        threshold = -math.inf

        while True:
            active = [e for e in entries if e["cursor"] < len(e["ids"])]
            if not active:
                break
            active.sort(key=lambda e: e["ids"][e["cursor"]])

            # 找 pivot：前缀上界和超过门槛（同分看 id 字典序）。
            prefix = 0.0
            pivot_entry = None
            pivot_id = None
            for entry in active:
                prefix += entry["ub"]
                cur_id = entry["ids"][entry["cursor"]]
                if prefix > threshold or (
                    prefix == threshold
                    and (pivot_id is not None and cur_id < pivot_id)
                ):
                    pivot_entry = entry
                    pivot_id = cur_id
                    break

            if pivot_entry is None:
                break

            preceding = active[:active.index(pivot_entry)]
            if all(e["ids"][e["cursor"]] == pivot_id for e in preceding):
                # 完整打分。
                score = 0.0
                length = self._doc_len[pivot_id]
                norm_den = self.k1 * (1.0 - self.b + self.b * length / avgdl)
                for entry in entries:
                    freq = entry["posting"].get(pivot_id)
                    if freq:
                        idf = entry["idf"]
                        score += (
                            idf
                            * freq
                            * (self.k1 + 1.0)
                            / (freq + norm_den)
                        )
                self._scored += 1
                if score > 0.0:
                    key = (score, _RevStr(pivot_id))
                    if len(heap) < k:
                        heapq.heappush(heap, key)
                        if len(heap) == k:
                            threshold = heap[0][0]
                    elif key > heap[0]:
                        heapq.heapreplace(heap, key)
                        threshold = heap[0][0]

                # 指向 pivot 的链全部前进一步（pivot 之后的链不动）。
                for entry in active:
                    if entry["ids"][entry["cursor"]] == pivot_id:
                        entry["cursor"] += 1
            else:
                # 浅层推进：第一条落后的链直接跳到 pivot。
                laggard = next(
                    e for e in preceding
                    if e["ids"][e["cursor"]] < pivot_id
                )
                laggard["cursor"] = bisect_ge(
                    laggard["ids"], laggard["cursor"], pivot_id
                )

        ranked = sorted(heap, key=lambda item: (-item[0], str(item[1])))
        return [(str(rev), score) for score, rev in ranked]

    # ---- 状态 -----------------------------------------------------

    def df(self, term):
        """词项的文档频率，查不到给 0。"""
        posting = self._postings.get(term)
        return len(posting) if posting else 0

    def avgdl(self):
        """平均文档长度（按 rank_tokens 计数），空库给 0.0。"""
        n = len(self._doc_len)
        return self._total_len / n if n else 0.0

    def stats(self):
        """索引状态：篇数、词表规模、总词数、平均长度、累计打分数。"""
        n = len(self._doc_len)
        return {
            "docs": n,
            "terms": len(self._postings),
            "total_len": self._total_len,
            "avgdl": self._total_len / n if n else 0.0,
            "scored": self._scored,
        }


def bisect_ge(ids, cursor, target):
    """返回 ids 中第一个 >= target 的下标（从 cursor 起找）。"""
    lo, hi = cursor, len(ids)
    while lo < hi:
        mid = (lo + hi) // 2
        if ids[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo
