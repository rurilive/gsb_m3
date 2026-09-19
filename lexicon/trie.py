"""Trie 前缀补全。

insert 建库，complete 返回所有以 prefix 开头的词，
按 freq 降序排列，同频按词的字典序。
fuzzy=k 时做模糊补全：距离口径为 prefix 与候选词任意前缀的
最小编辑距离（仅增删替换），距离不超过 k 即命中。
"""


class _Node:
    __slots__ = ("children", "word", "freq")

    def __init__(self):
        self.children = {}
        self.word = None  # 非 None 表示路径到此是一个完整词
        self.freq = 0


class Trie:
    """前缀树，支持按频次排序的前缀补全。"""

    def __init__(self):
        self._root = _Node()

    def insert(self, word, freq):
        """收录一个词；重复收录覆盖 freq。"""
        if not word:
            raise ValueError("word must be non-empty")
        node = self._root
        for ch in word:
            node = node.children.setdefault(ch, _Node())
        node.word = word
        node.freq = freq

    def complete(self, prefix, fuzzy=None):
        """返回命中词。

        fuzzy=None：精确前缀补全，freq 降序，同频按字典序。
        fuzzy=k（非负整数）：prefix 与候选词任意前缀的最小编辑距离
        （增删替换）不超过 k 即命中；按距离升序、freq 降序、字典序排列。
        k=0 等价于精确前缀补全。
        """
        if fuzzy is None:
            node = self._walk(prefix)
            if node is None:
                return []
            found = self._collect(node)
            found.sort(key=lambda item: (-item[1], item[0]))
            return [w for w, _ in found]
        if not isinstance(fuzzy, int) or isinstance(fuzzy, bool) or fuzzy < 0:
            raise ValueError("fuzzy must be a non-negative integer or None")
        hits = {}  # word -> (distance, freq)，同一词只保留最小距离
        first_row = list(range(len(prefix) + 1))
        self._fuzzy_search(self._root, first_row, first_row[-1], prefix, fuzzy, hits)
        ordered = sorted(
            hits.items(), key=lambda item: (item[1][0], -item[1][1], item[0])
        )
        return [w for w, _ in ordered]

    def _walk(self, prefix):
        node = self._root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def _fuzzy_search(self, node, prev_row, path_best, prefix, k, hits):
        """沿 Trie 深度优先，逐层计算编辑距离 DP 行。

        prev_row[i] = prefix[:i] 与当前路径串的编辑距离；
        path_best 为路径上各节点 DP 行末列（完整 prefix 对路径前缀的
        距离）的历史最小值，即该候选词任意前缀上的最小距离。
        """
        if node.word is not None and path_best <= k:
            distance = path_best
            old = hits.get(node.word)
            if old is None or distance < old[0]:
                hits[node.word] = (distance, node.freq)
        for ch, child in node.children.items():
            cur_row = [prev_row[0] + 1]
            for i, pch in enumerate(prefix, start=1):
                cost = 0 if pch == ch else 1
                cur_row.append(
                    min(
                        prev_row[i] + 1,        # 删除
                        cur_row[i - 1] + 1,     # 插入
                        prev_row[i - 1] + cost,  # 匹配/替换
                    )
                )
            child_best = min(path_best, cur_row[-1])
            # 完整 prefix 对路径前缀的距离与各行最小距离都 >k 时，
            # 后续路径不可能再降到 k，整棵子树剪枝。
            if min(cur_row) <= k or child_best <= k:
                self._fuzzy_search(
                    child, cur_row, child_best, prefix, k, hits
                )

    @staticmethod
    def _collect(node):
        found = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.word is not None:
                found.append((cur.word, cur.freq))
            stack.extend(cur.children.values())
        return found
