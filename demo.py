"""kmpmatch 现状演示。

第一段：用逐位对齐比较求出现位置与多模式结果，用逐候选重算求前缀
长度数组与最小周期，并打印比较次数；
第二段：预留的失配函数线性匹配与独立交叉核对的演示位子（见文末注释）。
"""

from kmpmatch.naive import (
    TextTools,
    min_period,
    occurrences,
    occurrences_many,
    prefix_naive,
)


def main():
    print("=== 朴素逐位比较 ===")
    text = "aabaab"
    print("  文本 %s" % text)
    print("  前缀长度数组 ababaca %s" % (prefix_naive("ababaca"),))
    print("  最小周期 aabaab %d" % min_period("aabaab"))
    print("  模式 ab 位置 %s" % (occurrences("ab", text),))
    print("  多模式 ab aa 位置 %s" % (occurrences_many(["ab", "aa"], text),))

    tools = TextTools(text)
    tools.reset_compare_count()
    tools.occurrences("ab")
    print("  逐字符比较次数 %d" % tools.compare_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 kmpmatch 里补出以失配函数为基础的线性匹配之后，在这里加一段演示：
    # 用一次扫描给出全部出现位置，与上面逐位比较的位置逐项对照；再由同一
    # 失配函数导出最短周期与循环节判定，并与逐位试的结果对照；另用独立的
    # 交叉核对口径与多模式自动机口径各求一遍位置，几条路互相印证；打印线
    # 性匹配比较次数与朴素比较次数的差距；最后覆盖空文本、单字符、全相同
    # 字符、无匹配、模式等于文本、模式长于文本、含分隔符的串、单字符周期
    # 这些边界，确认各条路径结论一致。

    print("  朴素查找 ab 位置 %s" % (occurrences("ab", text),))


if __name__ == "__main__":
    main()
