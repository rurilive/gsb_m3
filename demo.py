"""palx 现状演示。

第一段：朴素实现——把子串切片反转后整体比较判断是否回文，再枚举全部子串求
最长回文子串、统计回文子串个数、求最小回文划分与回文划分方案数。
第二段：预留的马拉车（回文半径）演示位子（见文末注释）。
"""

from palx import PalindromeTools


def main():
    print("=== 朴素切片反转比求回文结果 ===")
    tools = PalindromeTools("banana")
    print(f"  文本 -> {tools.text()}")
    print(f"  子串[1,4) 是否回文 -> {tools.is_palindrome(1, 4)}")
    print(f"  子串[0,3) 是否回文 -> {tools.is_palindrome(0, 3)}")
    tools.longest_palindrome()
    print(f"  中心扩展比较次数 -> {tools.expand_steps()}")
    print(f"  最长回文子串 -> {tools.longest_palindrome()}")
    print(f"  回文子串总个数 -> {tools.count_palindromes()}")
    print(f"  最小回文划分段数 -> {tools.min_palindrome_cut()}")
    print(f"  回文划分方案总数 -> {tools.count_palindrome_cut()}")

    # TODO: 第二段演示（实现后补）
    # 以马拉车（回文半径）为核心，一次线性扫描求出每个中心的最长回文半径（奇偶
    # 两种中心统一处理），由此常数级判定任意子串是否回文，并统计全部回文子串个数
    # 与最长回文子串；在回文半径之上做最小回文划分与回文划分计数。实现后在这里加
    # 一段演示：用同一批文本跑线性路径，打印子串判等、回文个数、最长回文、最小划分
    # 与划分计数，并与上面的朴素结果逐项对照，同时暴露中心扩展次数与线性扫描的差距。


if __name__ == "__main__":
    main()
