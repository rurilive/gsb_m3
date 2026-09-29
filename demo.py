"""indexly 现状演示。

第一段：用朴素线性扫描搭几篇文档，查一个词，看命中文档与词频。
第二段：预留的倒排索引、布尔检索与打分排序演示位子（见文末注释）。
"""

from indexly import LinearDocs


def main():
    print("=== 朴素线性扫描（现有能力） ===")
    docs = LinearDocs()
    docs.add("a", "the quick brown fox")
    docs.add("b", "quick quick brown bear")
    docs.add("c", "lazy dogs sleep")
    print("  文档 ->", docs.doc_ids())
    print("  search quick ->", docs.search("quick"))
    print("  search brown ->", docs.search("brown"))
    print("  count quick ->", docs.count("quick"))
    print("  search zebra ->", docs.search("zebra"))
    docs.remove("b")
    print("  删掉 b 后 search quick ->", docs.search("quick"))

    # TODO(倒排索引改造): 倒排表、布尔检索、打分排序就位后在这里补一段演示：
    # 对同一批文档建好倒排索引，先查单个词打印命中文档与倒排表内容，再跑一轮
    # 带与或非与括号的多词布尔查询并打印结果，确认与朴素线性扫描的口径逐项
    # 一致；最后对某个词跑一次打分检索，打印按分数降序的文档名单与各自得分，
    # 让相关文档排在前面这件事在输出里直接看得见。


if __name__ == "__main__":
    main()
