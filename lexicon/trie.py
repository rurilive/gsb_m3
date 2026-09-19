"""Trie 前缀补全。

insert 建库，complete 返回所有以 prefix 开头的词，
按 freq 降序排列，同频按词的字典序。
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

    def complete(self, prefix):
        """返回所有以 prefix 开头的词，freq 降序；同频按字典序。"""
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
