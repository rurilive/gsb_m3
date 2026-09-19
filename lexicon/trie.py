"""Trie 前缀补全。

insert 建库，complete 返回所有以 prefix 开头的词，
按 freq 降序排列，同频按词的字典序。

complete(prefix, fuzzy=k) 时做模糊补全：编辑距离只算增删替换，
距离口径为 prefix 与候选词任意前缀的最小编辑距离，不超过 k 即命中。
"""


class _Node:
    __slots__ = ("children", "word", "freq")

    def __init__(self):
        self.children = {}
        self.word = None  # 非 None 表示路径到此是一个完整词
        self.freq = 0


class Trie:
    """前缀树，支持按频次排序的前缀补全与编辑距离模糊补全。"""

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
        """前缀补全；fuzzy=k 时按最小编辑距离 <= k 模糊召回。

        fuzzy=None 保持精确前缀补全：freq 降序，同频按字典序。
        fuzzy=k（非负整数）时：命中词按距离升序、freq 降序、字典序排列；
        k=0 严格等价于精确前缀补全。
        """
        if fuzzy is not None:
            if isinstance(fuzzy, bool) or not isinstance(fuzzy, int) or fuzzy < 0:
                raise ValueError("fuzzy must be a non-negative int or None")
            found = self._fuzzy_collect(prefix, fuzzy)
            found.sort(key=lambda item: (item[2], -item[1], item[0]))
            return [w for w, _, _ in found]
        node = self._walk(prefix)
        if node is None:
            return []
        found = self._collect(node)
        found.sort(key=lambda item: (-item[1], item[0]))
        return [w for w, _ in found]

    def _walk(self, prefix):
        node = self._root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

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

    def _fuzzy_collect(self, prefix, k):
        """DFS 整棵树，沿途维护 prefix 对当前路径的 Levenshtein DP 行。

        每个词的距离取根到该词路径上各行末值的最小值，
        即 prefix 与该词任意前缀的最小编辑距离。
        返回 (word, freq, dist) 三元组列表。
        """
        columns = len(prefix) + 1
        first_row = list(range(columns))
        found = []
        stack = [(self._root, first_row, first_row[-1])]
        while stack:
            node, prev_row, best = stack.pop()
            if node.word is not None and best <= k:
                found.append((node.word, node.freq, best))
            if best > k and min(prev_row) > k:
                # 路径上各行末值的下界已超过 k，子树不可能再命中，剪枝
                continue
            for ch, child in node.children.items():
                row = [prev_row[0] + 1]
                for i in range(1, columns):
                    cost = 0 if prefix[i - 1] == ch else 1
                    row.append(min(
                        row[i - 1] + 1,          # 插入
                        prev_row[i] + 1,         # 删除
                        prev_row[i - 1] + cost,  # 替换/相同
                    ))
                stack.append((child, row, min(best, row[-1])))
        return found
