"""indexly 的现有实现。

这里只有一套最朴素的线性扫描：文档按加入顺序排在一个列表里，检索时
从第一篇扫到最后一篇，对每篇文档的原文逐词判断是否含有查询词。没有
分词表，没有倒排表，没有打分，没有多词布尔，删掉一篇文档也只是从列表
里去掉，因为压根没有需要跟着维护的索引结构。
"""


class LinearDocs:
    """朴素线性扫描的文档集。

    只做一件确定的事：按顺序把文档留着，查词时逐篇扫。文档少的时候够
    用，文档一多每次检索都要从头扫到尾；多词条件只能调用方自己写循环
    去拼，相关度也无法表达。
    """

    def __init__(self):
        self._order = []
        self._texts = {}

    def add(self, doc_id, text):
        """按文档名加入一篇文档，保留加入顺序。

        doc_id 必须是非空字符串且不能重复，否则抛 ValueError。text 必须
        是字符串，否则抛 ValueError。
        """
        if not isinstance(doc_id, str) or not doc_id:
            raise ValueError("doc_id must be a non-empty str")
        if doc_id in self._texts:
            raise ValueError("duplicate doc_id: %s" % doc_id)
        if not isinstance(text, str):
            raise ValueError("text must be a str")
        self._texts[doc_id] = text
        self._order.append(doc_id)

    def remove(self, doc_id):
        """按文档名删掉一篇文档。不存在则抛 ValueError。"""
        if doc_id not in self._texts:
            raise ValueError("unknown doc_id: %s" % doc_id)
        del self._texts[doc_id]
        self._order.remove(doc_id)

    def doc_ids(self):
        """按加入顺序返回全部文档名。"""
        return list(self._order)

    def text(self, doc_id):
        """按文档名取回原文。不存在则抛 ValueError。"""
        if doc_id not in self._texts:
            raise ValueError("unknown doc_id: %s" % doc_id)
        return self._texts[doc_id]

    def search(self, word):
        """找出原文按词包含给定查询词的文档。

        对每篇文档逐词扫描，命中即记下，结果按加入顺序返回。word 必须是
        非空字符串，否则抛 ValueError。大小写敏感，不看词边界之外的语义，
        也不做任何排序。
        """
        if not isinstance(word, str) or not word:
            raise ValueError("word must be a non-empty str")
        hits = []
        for doc_id in self._order:
            for token in self._texts[doc_id].split():
                if token == word:
                    hits.append(doc_id)
                    break
        return hits

    def count(self, word):
        """统计某个词在所有文档原文里出现的总次数（逐词计数）。

        word 必须是非空字符串，否则抛 ValueError。
        """
        if not isinstance(word, str) or not word:
            raise ValueError("word must be a non-empty str")
        total = 0
        for doc_id in self._order:
            for token in self._texts[doc_id].split():
                if token == word:
                    total += 1
        return total
