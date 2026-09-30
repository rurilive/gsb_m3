"""seqalign 现状演示。

第一段：用一对小串看朴素枚举给出的最长公共子序列、编辑距离、只允许插入删除
的距离，以及最长公共子串与最长公共前缀。
第二段：预留的升级演示位子（见文末注释）。
"""

from seqalign import SeqAlign


def main():
    print("=== 序列比对与编辑距离（现有朴素枚举能力） ===")
    s = SeqAlign()
    a = "kitten"
    b = "sitting"
    print(f"  a = {a}")
    print(f"  b = {b}")
    print(f"  最长公共子序列长度 = {s.lcs_length(a, b)}")
    print(f"  一条最长公共子序列 = {s.lcs_string(a, b)!r}")
    print(f"  编辑距离 = {s.edit_distance(a, b)}")
    print(f"  只允许插入删除的距离 = {s.indel_distance(a, b)}")
    print(f"  最长公共子串长度 = {s.lcs_substring(a, b)}")
    print(f"  最长公共前缀长度 = {s.lcs_prefix(a, b)}")

    # TODO: 第二段演示（实现后补）
    # 二维动态规划、滚动数组与规模计数实现后，在这里加一段演示：把动态规划
    # 路径与朴素枚举路径的最长公共子序列长度、编辑距离、只允许插入删除的距离、
    # 最长公共子串与最长公共前缀并排打印，并把两边的状态数差距一并打印出来。


if __name__ == "__main__":
    main()
