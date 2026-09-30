"""zstr 现状演示。

第一段：用逐位直接比较求 Z 数组、出现位置与最小周期，并打印比较次数；
第二段：预留的 Z 函数与扩展 KMP 演示位子（见文末注释）。
"""

from zstr.naive import TextTools, min_period, occurrences, z_array


def main():
    print("=== 朴素逐位比较 ===")
    text = "aabaab"
    tools = TextTools(text)
    print("  文本 %s" % text)
    print("  Z 数组 %s" % (z_array(text),))
    print("  最小周期 %d 是否整周期 %s"
          % (min_period(text), tools.is_periodic()))

    tools.reset_compare_count()
    print("  模式 ab 位置 %s" % (tools.occurrences("ab"),))
    print("  逐字符比较次数 %d" % tools.compare_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 zstr 里补出线性 Z 函数与扩展 KMP 之后，在这里加一段演示：对同一段
    # 文本一趟求出全部 Z 值，再在模式加分隔符加文本上求出现位置，与上面逐位
    # 比较的位置逐项对照；另用前缀函数独立求一遍位置与最小周期，两条新路互
    # 相印证；打印 Z 函数比较次数与朴素比较次数的差距；最后覆盖空串、单字符、
    # 全相同字符、无匹配、模式等于文本、模式长于文本、含分隔符的串、单字符
    # 周期这些边界，确认各条路径结论一致。

    print("  朴素查找 ab 位置 %s" % (occurrences("ab", text),))


if __name__ == "__main__":
    main()
