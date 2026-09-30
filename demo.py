"""editpath 现状演示。

第一段：朴素实现求编辑距离与最长公共子序列、最长公共子串。
第二段：预留的二维动态规划路径与朴素路径一致性对照的演示位子。
"""

from editpath.core import EditPath


def main():
    print("=== 朴素编辑距离与序列对齐（现有能力） ===")
    ep = EditPath()
    pairs = [("kitten", "sitting"), ("flaw", "lawn"), ("", "abc"), ("abc", "abc")]
    for a, b in pairs:
        dist = ep.edit_distance(a, b)
        print("  源", repr(a), "目标", repr(b), "编辑距离 =", dist)
    print("  最长公共子序列长度 =", ep.lcs_length("abcde", "ace"))
    print("  最长公共子串长度 =", ep.lcs_substring("abcdef", "zabcf"))
    print("  最长公共前缀长度 =", ep.lcs_prefix("abcdef", "abcxyz"))
    print("  只增删距离 =", ep.indel_distance("abc", "abd"))
    print("  带权距离 =", ep.weighted_distance("kitten", "sitting", 1, 1, 1))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
