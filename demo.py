"""NaiveSuffix 现状演示。

第一段跑基线功能：后缀枚举排序、不同子串计数、最长公共前缀、线性查找。
第二段是后缀数组相关演示的占位（见文末注释），尚未实现。
"""

from suffixx.table import NaiveSuffix


def main():
    print("=== 基线功能（朴素实现） ===")
    t = NaiveSuffix("banana")
    print(f"  text        = {t.text!r}")
    print(f"  suffixes()  = {t.suffixes()}")
    print(f"  distinct    = {t.count_distinct_substrings()}")
    print(f"  lcp(1, 3)   = {t.longest_common_prefix_of_suffixes(1, 3)}")
    print(f"  find('ana') = {t.find('ana')}")

    # TODO: 第二段演示（实现后补）
    # 后缀数组构造、名次数组与高度数组、常数级 lcp 查询、由高度数组求
    # 不同子串个数、以及用后缀数组二分查找一个模式的全部位置。


if __name__ == "__main__":
    main()
