"""palindromex 的演示脚本。

第一段直接跑基线功能，打印一个固定串上的几项事实。第二段留给改造后的线性
结构来演示，现在只有一个占位注释。
"""

from palindromex.pal import BrutePal

TEXT = "abaxyzzyxf"


def main():
    p = BrutePal(TEXT)
    print("文本:", TEXT)
    print("最长回文:", p.longest_palindrome())
    print("回文子串总数:", p.count_palindromes())
    print("是否回文 [0,3):", p.is_palindrome(0, 3))
    print("中心 11 的半径:", p.each_center_max(11))


# TODO: 第二段演示（实现后补）
# 改造完成后在这里补一轮：最长回文、本质不同回文子串计数与全中心半径数组。


if __name__ == "__main__":
    main()
