"""模糊检索倒排索引的朴素实现。

当前只有精确整词匹配，而且匹配靠的是一次线性扫描：命中不光取决于词本身，
还要看这份文档有没有把该词加进去。没有倒排表，前缀查询与编辑距离模糊查询
都没有入口，删词留下的空洞也无从清理。
"""


class FuzzyIndex:
    """精确整词匹配的倒排索引，倒排当前以线性扫描代替。

    里头维护两张平行的映射：词到文档、文档到词，两边逐项对齐，
    写入时同步登记，删除时同步注销。
    """

    def __init__(self):
        # 词 -> 该词所属文档集合
        self._postings = {}
        # 文档 -> 该文档登记过的词集合
        self._docs = {}
        # 查询逐条走过的倒排项数，用来证明查询到底扫了多少
        self._access = 0

    # --- 写入 ---

    def add_doc(self, doc_id, terms):
        """把一份文档及其词表登记进索引。

        同名文档重复登记时，先整体注销该文档的旧词，再按新词表重新登记，
        等价于一次覆盖写。返回该文档最终登记的词数。
        """
        if doc_id in self._docs:
            self.remove_doc(doc_id)
        owned = set(terms)
        self._docs[doc_id] = owned
        for term in owned:
            if term not in self._postings:
                self._postings[term] = set()
            self._postings[term].add(doc_id)
        return len(owned)

    def remove_doc(self, doc_id):
        """注销一份文档，返回是否真的删掉了。"""
        owned = self._docs.pop(doc_id, None)
        if owned is None:
            return False
        for term in owned:
            bucket = self._postings.get(term)
            if bucket is not None:
                bucket.discard(doc_id)
                if not bucket:
                    del self._postings[term]
        return True

    # --- 基本属性 ---

    @property
    def access_count(self):
        """自上次归零以来，查询逐条走过的倒排项数。"""
        return self._access

    def reset_access_count(self):
        """把访问计数归零。"""
        self._access = 0

    def doc_count(self):
        """已登记文档数。"""
        return len(self._docs)

    def term_count(self):
        """词表里不同词的个数。"""
        return len(self._terms())

    def terms(self):
        """按字典序返回词表副本。"""
        return sorted(self._terms())

    def _terms(self):
        """收集当前仍然挂着文档的词。"""
        out = []
        for term, bucket in self._postings.items():
            if bucket:
                out.append(term)
        return out

    def docs_for(self, term):
        """精确整词匹配：线性走一遍词表，命中就问该词的倒排要文档集合。

        这条路每查一次都要把当前词表过一遍，访问计数加的是词表大小，
        跟命中多少没有任何关系。
        """
        out = set()
        for word, bucket in self._postings.items():
            self._access += 1
            if word == term:
                out |= set(bucket)
        return out

    def doc_terms(self, doc_id):
        """给出一份文档登记过的词，按字典序返回副本。"""
        return sorted(self._docs.get(doc_id, set()))