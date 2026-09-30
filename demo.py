"""eertree 现状演示。

第一段：拿一段小文本，用枚举子串的朴素路子看某个子串是否回文、全部回文
子串、本质不同回文个数、以每个位置为结尾的回文个数与最长回文长度；
第二段：预留的回文自动机改造演示位子（见文末注释）。
"""

from eertree.tree import BrutePalTree


def main():
    print("=== 朴素回文子串工具 ===")
    t = BrutePalTree("ababa")
    print("  文本 %s，长度 %d" % (t.text, len(t)))
    print("  aba 是回文吗 %s" % t.is_pal("aba"))
    print("  ab 是回文吗 %s" % t.is_pal("ab"))
    print("  全部回文子串 %s" % t.palindromic_substrings())
    print("  本质不同回文个数 %d" % t.distinct_pal_count())
    print("  以每个位置为结尾的回文个数 %s"
          % [t.pal_count_by_end(i) for i in range(len(t))])
    print("  以每个位置结尾的最长回文长度 %s"
          % [t.longest_pal_suffix(i) for i in range(len(t))])
    print("  ababa 出现过吗 %s" % t.contains_pal("ababa"))
    print("  aa 出现过吗 %s" % t.contains_pal("aa"))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
