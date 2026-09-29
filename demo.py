"""multimatch 现状演示。

第一段：看现有逐模式扫描在几个模式上的查找结果。
第二段：预留的迭代演示位子（见文末注释）。
"""

from multimatch import EachPattern


def baseline_demo():
    matcher = EachPattern(["he", "she", "hers"])
    text = "ushers"

    print("=== 逐模式扫描（现有能力） ===")
    print("  patterns()        ->", matcher.patterns())
    print("  find(%r) ->" % (text,))
    for m in matcher.find(text):
        print("      %r 起 %d 止 %d" % (m.pattern, m.start, m.end))
    print("  说明：现在每个模式各跑一遍朴素子串查找，没有前缀共享，也没有一次遍历。")


# TODO(多模式自动机改造): 字典树、失配指针与输出集合就位后，在这里补一段演示：
# 用同一组有互为子串的模式（例如 he、she、hers、his）建一台自动机，
# 演示文本只被遍历一次就报出全部出现，重叠与嵌套的模式都命中，
# 演示增删模式后匹配结果与重建口径一致。


if __name__ == "__main__":
    baseline_demo()
