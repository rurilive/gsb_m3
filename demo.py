"""hashx 现状演示。

第一段：朴素实现——逐字符比判断子串相等，再枚举子串对求最长重复子串、
最长回文子串与两串最长公共子串。
第二段：预留的滚动哈希演示位子（见文末注释）。
"""

from hashx import StringTools


def main():
    print("=== 朴素逐字符比求子串结果 ===")
    tools = StringTools("banana")
    print(f"  文本 -> {tools.text()}")
    print(f"  子串[1,4) 与 [3,6) 是否相等 -> {tools.equal(1, 4, 3, 6)}")
    print(f"  子串[0,3) 与 [1,4) 是否相等 -> {tools.equal(0, 3, 1, 4)}")
    print(f"  最长重复子串 -> {tools.longest_repeat()}")
    print(f"  最长回文子串 -> {tools.longest_palindrome()}")
    print(f"  与 abracadabra 的最长公共子串 -> "
          f"{tools.longest_common_substring('abracadabra')}")

    # TODO: 第二段演示（实现后补）
    # 以多项式前缀哈希与幂表为核心，预处理后任意子串哈希可常数级取出，子串判等、
    # 查找重复子串、求最长公共前缀、二分加哈希求最长回文、求两串最长公共子串都降
    # 一个量级。实现后在这里加一段演示：用同一批文本跑哈希路径，打印子串判等、
    # 最长重复子串、最长公共前缀、最长回文、最长公共子串，并与上面的朴素结果逐项对照。


if __name__ == "__main__":
    main()
