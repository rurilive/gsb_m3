"""suflcp 现状演示。

第一段：对一个短文本用朴素做法取出后缀数组与相邻最长公共前缀，再逐字符
现算任意两个后缀的最长公共前缀；
第二段：预留的倍增构造、卡萨伊线性扫描与稀疏表查询演示位子（见文末注释）。
"""

from suflcp.engine import SuffixArray, naive_lcp_array, common_prefix_len


def main():
    text = "banana"
    print("=== 朴素后缀数组与最长公共前缀 ===")
    print("  文本 %s" % text)

    sa = SuffixArray(text)
    print("  后缀数组 %s" % (sa.suffix_array(),))
    for start in sa.suffix_array():
        print("    下标 %d 后缀 %s" % (start, repr(text[start:])))

    print("  相邻最长公共前缀 %s" % (naive_lcp_array(text),))
    print("  排名逆表 %s" % (sa.rank(),))

    print("  任意两后缀 1 与 3 的最长公共前缀 %d" % common_prefix_len(text, 1, 3))
    print("  任意两后缀 0 与 2 的最长公共前缀 %d" % common_prefix_len(text, 0, 2))
    print("  文本 %s 与 %s 的最长公共前缀 %d"
          % ("", "空", common_prefix_len("", 0, 0)))

    # TODO(倍增与卡萨伊): 在 suflcp 里补出用二的幂长度逐步排序、以排名为
    # 键的倍增法后缀数组，排名的比较要能线性完成；再补出卡萨伊扫描，借后缀
    # 数组与排名在整体线性时间里求相邻最长公共前缀；再把前缀数组压成区间最
    # 小值结构（稀疏表或笛卡尔树），支撑任意两个后缀的最长公共前缀查询。同
    # 时另起一条独立做法：朴素排序后缀并逐字符比对，在固定输入上与新路逐项
    # 一致。实现之后在这里加一段演示：先对一段长文本跑倍增建后缀数组并打印，
    # 再打印卡萨伊扫描得到的相邻前缀数组，接着随机取若干对后缀，用区间最小
    # 值查询与逐字符现算分别求最长公共前缀，打印两边结果确认一致；最后覆盖
    # 空串、单字符、全相同字符、无重复字符、有公共前后缀这几个边界并打印。


if __name__ == "__main__":
    main()
