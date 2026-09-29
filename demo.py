"""matchx 现状演示。

第一段：跑通朴素查找的现有能力（可运行）。
第二段：预留的迭代演示位子（见文末注释）。
"""

from matchx.search import (
    InvalidPatternError,
    MatchError,
    NaiveSearch,
    find,
    find_all,
    has,
    count,
)


def main():
    print("=== 朴素查找（现有能力） ===")
    text = "abababab"
    pat = "abab"
    print(f"  find({text!r}, {pat!r})     -> {find(text, pat)}")
    print(f"  find_all({text!r}, {pat!r}) -> {find_all(text, pat)}")
    print(f"  has({text!r}, {pat!r})      -> {has(text, pat)}")
    print(f"  count({text!r}, {pat!r})    -> {count(text, pat)}")

    print("  无命中示例：", find("abcdef", "zz"))
    print("  重叠示例：  ", find_all("aaaa", "aa"))

    s = NaiveSearch()
    degenerate = "a" * 50
    s.find(degenerate, "a" * 20 + "b")
    print(f"  退化场景比较次数 -> {s.comparisons}（文本长度仅 {len(degenerate)}）")

    try:
        find("abc", "")
    except MatchError as exc:
        print(f"  空模式 fail fast -> {type(exc).__name__}")
    assert issubclass(InvalidPatternError, ValueError)

    # TODO: 第二段演示（实现后补）
    # 线性匹配改造完成后，在这里补一段演示：
    # 打印某固定模式的前缀函数取值、用线性算法现场扫出全部出现位置、
    # 一次扫描完成的多模式匹配结果，以及一个字符串的最小循环节；
    # 并把线性算法的字符比较次数与上面朴素实现的退化数字放在一起对比。


if __name__ == "__main__":
    main()
