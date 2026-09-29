"""fuzzyidx 现状演示。

第一段：建一份小索引，用精确整词匹配查一个词，看到命中文档与访问计数；
第二段：预留的前缀与模糊检索演示位子（见文末注释）。
"""

from fuzzyidx.index import FuzzyIndex


def main():
    print("=== 精确整词匹配 ===")
    idx = FuzzyIndex()
    idx.add_doc(1, ["apple", "apply", "ape"])
    idx.add_doc(2, ["banana", "band"])
    idx.add_doc(3, ["apple", "pineapple"])
    idx.reset_access_count()
    hit = idx.docs_for("apple")
    print("  文档数 %d，词表大小 %d" % (idx.doc_count(), idx.term_count()))
    print("  命中 apple 的文档 %s，访问计数 %d" % (sorted(hit), idx.access_count))
    print("  词表 %s" % (idx.terms(),))

    # TODO(前缀与模糊检索): 在 FuzzyIndex 里补出前缀倒排与有界编辑距离模糊检索
    # 之后，在这里加一段演示：先做一次前缀查询取回以某前缀起头的文档，
    # 再做一次 fuzzy(term, max_dist) 取回距离不超过 max_dist 的候选并按词频
    # 或距离排好序，打印结果，并比较访问计数说明模糊检索没有对每个词都跑一遍
    # 完整编辑距离。


if __name__ == "__main__":
    main()
