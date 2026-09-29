"""朴素词表：改造前的基线实现。

WordList 内部只放一个字符串列表与一个词频字典，所有与前缀有关的查询
都靠线性扫描完成。实现刻意保持朴素，作为前缀树改造前的基线行为。
"""

__all__ = ["WordList"]


class WordList:
    """朴素字符串词表。

    内部维护两个结构：
      - _items：按插入顺序保存的词条列表，重复插入会保留重复项
      - _freq：词频字典，记录每个词被插入过的次数

    所有查询（包含判断、前缀判断、前缀收集、词频）都在列表上线性完成。
    """

    def __init__(self):
        self._items = []
        self._freq = {}

    def insert(self, word):
        """登记一个词，词频加一。返回词频加一后的值。"""
        self._items.append(word)
        self._freq[word] = self._freq.get(word, 0) + 1
        return self._freq[word]

    def contains(self, word):
        """判断词是否出现过（词频大于零）。"""
        return self._freq.get(word, 0) > 0

    def starts_with(self, prefix):
        """是否存在某个词以 prefix 为前缀。"""
        for item in self._items:
            if item.startswith(prefix):
                return True
        return False

    def remove(self, word):
        """词频减一，并从列表中删去该词的一个副本。

        词的计数本来为零时返回 False 且不改动结构；否则减一、
        在列表中删掉一个副本并返回 True。
        """
        if self._freq.get(word, 0) <= 0:
            return False
        self._freq[word] -= 1
        self._items.remove(word)
        return True

    def count(self, word):
        """返回词的词频，未登记过的词返回零。"""
        return self._freq.get(word, 0)

    def words_with_prefix(self, prefix):
        """按插入顺序收集所有以 prefix 为前缀的词（重复项保留）。"""
        result = []
        for item in self._items:
            if item.startswith(prefix):
                result.append(item)
        return result

    def __len__(self):
        """当前登记的词条总数，含重复项。"""
        return len(self._items)

    def __contains__(self, word):
        return self.contains(word)
