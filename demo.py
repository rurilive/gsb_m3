"""NaiveSubstrings 现状演示。

第一段跑基线朴素功能：枚举全部子串、集合去重计数、判断模式是否子串、
线性扫描计数、按长度聚合。第二段是后缀自动机相关演示的占位（见文末
注释），尚未实现。
"""

from samx.substrings import NaiveSubstrings


def main():
    print("=== 基线功能（朴素实现） ===")
    t = NaiveSubstrings("banana")
    print(f"  text                = {t.text!r}")
    print(f"  全部子串个数        = {len(t.all_substrings())}")
    print(f"  不同子串个数        = {t.count_distinct_substrings()}")
    print(f"  是否子串('nan')     = {t.is_substring('nan')}")
    print(f"  出现次数('ana')     = {t.count_occurrences('ana')}")
    print(f"  出现次数('a')       = {t.count_occurrences('a')}")
    print(f"  按长度聚合          = {t.count_substrings_by_length()}")
    print(f"  不同子串长度        = {t.distinct_substring_lengths()}")

    # TODO: 第二段演示（实现后补）
    # 在线增量构造后缀自动机、每个状态的出现次数聚合、用状态最长子串
    # 长度减去链接状态最长子串长度求不同子串个数、模式判定与出现次数、
    # 全部不同子串的长度与前缀聚合，以及两串最长公共子串等扩展能力。


if __name__ == "__main__":
    main()
