"""autocmplt 的朴素全量扫描补全实现（改造前的现状）。

现在只有一条检索路径：把每个词拿出来，用 str.startswith 判断是不是
以给定前缀开头，命中的词收进候选表，再按热度（计数）降序排一遍。
没有字典树，没有子树聚合计数，没有 Top-K 剪枝，也没有模糊匹配。
字典树检索、热度排序、Top-K 截断、增量学习、模糊补全与序列化见任务描述。
"""


class Autocomplete:
    """一撮带热度的词，补全只有全量扫描这一种。"""

    def __init__(self):
        self._counts = {}
        self._order = []
        self._last_scans = 0

    def add(self, word, count=1):
        """加入一个词，重复加入就叠加热度，返回这个词。"""
        if not isinstance(word, str) or word == "":
            raise ValueError("word must be a non-empty str")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("count must be a non-negative int")
        if word not in self._counts:
            self._counts[word] = 0
            self._order.append(word)
        self._counts[word] += count
        return word

    def remove(self, word):
        """按词删掉一个词，词不存在就报 KeyError。"""
        if word not in self._counts:
            raise KeyError(word)
        del self._counts[word]
        self._order.remove(word)

    def learn(self, word):
        """记录一次选用，把这个词的热度加一，词不存在就报 KeyError。"""
        if word not in self._counts:
            raise KeyError(word)
        self._counts[word] += 1
        return self._counts[word]

    def words(self):
        """按加入顺序返回所有词。"""
        return tuple(self._order)

    def count_of(self, word):
        """取回某个词的热度，词不存在就报 KeyError。"""
        if word not in self._counts:
            raise KeyError(word)
        return self._counts[word]

    def __len__(self):
        return len(self._counts)

    def __contains__(self, word):
        return word in self._counts

    def candidates(self, prefix):
        """返回以 prefix 开头的所有词，按热度降序、同热度按字典序升序。

        这一步把每个词都看一遍，命中与否都算一次扫描，扫过的词数记在
        scans() 里，方便观察全量扫描的代价。
        """
        if not isinstance(prefix, str):
            raise ValueError("prefix must be a str")
        hits = []
        self._last_scans = 0
        for word in self._order:
            self._last_scans += 1
            if word.startswith(prefix):
                hits.append(word)
        hits.sort(key=lambda w: (-self._counts[w], w))
        return hits

    def scans(self):
        """返回上一次 candidates 扫过的词数。"""
        return self._last_scans
