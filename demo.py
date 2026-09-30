"""trievocab 现状演示。

第一段: 建一份小词表, 看线性扫描下的前缀判定、前缀计数、完整单词判定、
按前缀取全部字符串与去重集合、最长公共前缀, 以及查询走过的字符比较步数。
第二段: 预留的字典树演示位子 (见文末注释)。
"""

from trievocab.vocab import FlatVocab


def main():
    print("=== 朴素词表 (线性扫描) ===")
    v = FlatVocab()
    for w in ("app", "apple", "app", "apricot", "bat", "banana", "band"):
        v.insert(w)

    print("  len                    = %d" % len(v))
    print("  all_words              = %s" % v.all_words())
    print("  contains(apple)        = %s" % v.contains("apple"))
    print("  has_prefix(ap)         = %s" % v.has_prefix("ap"))
    print("  count_prefix(ap)       = %d" % v.count_prefix("ap"))
    print("  words_with_prefix(ap)  = %s" % v.words_with_prefix("ap"))
    print("  distinct_with_prefix(b)= %s" % v.distinct_with_prefix("b"))
    print("  longest_common         = %s" % v.longest_common_prefix())

    v.reset_compare_count()
    v.count_prefix("ap")
    print("  count_prefix(ap) 的比较步数 = %d (词表大小 %d)" % (v.compare_count, len(v)))

    v.remove("app")
    print("  after remove(app), count_prefix(app) = %d" % v.count_prefix("app"))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
