"""朴素后缀工具。

当前实现只做两件事的朴素版本：把全部后缀枚举出来整体排序，
以及用集合把全部子串枚举去重后计数。子串查找是最朴素的线性扫描。
这些路径要么平方级要么线性扫描，子串去重还会先吃下一大块内存。
"""


class SuffixError(Exception):
    """后缀工具里所有错误的基类。"""


class IndexError_(SuffixError):
    """下标越界或下标类型非法。"""


class NaiveSuffix:
    """在一段文本上做朴素后缀操作的薄封装。

    文本一经构造即不可变；所有方法都是只读查询。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("text 必须是字符串")
        self._text = text

    def __repr__(self):
        return f"<NaiveSuffix {len(self._text)} chars>"

    def __len__(self):
        """文本长度。"""
        return len(self._text)

    @property
    def text(self):
        """构造时传入的原始文本。"""
        return self._text

    def _check_index(self, i, what="下标"):
        if not isinstance(i, int) or isinstance(i, bool):
            raise IndexError_(f"{what}必须是整数")
        if i < 0 or i >= len(self._text):
            raise IndexError_(f"{what}越界: {i}")

    def suffixes(self):
        """枚举全部后缀并按下标升序排列，返回下标序列。

        朴素做法：用下标切片出每一个后缀，整体排序，返回排序后
        每个后缀对应的起始下标。等长时按下标升序，保证结果确定。
        """
        n = len(self._text)
        order = sorted(range(n), key=lambda i: self._text[i:])
        return order

    def count_distinct_substrings(self):
        """用集合枚举全部子串去重后计数。

        朴素做法：两层循环把每个后缀的每个前缀都塞进集合，最后取大小。
        """
        seen = set()
        n = len(self._text)
        for i in range(n):
            for j in range(i + 1, n + 1):
                seen.add(self._text[i:j])
        return len(seen)

    def longest_common_prefix_of_suffixes(self, i, j):
        """逐字符比较两个后缀，返回最长公共前缀长度。"""
        self._check_index(i, "左下标")
        self._check_index(j, "右下标")
        n = len(self._text)
        k = 0
        while i + k < n and j + k < n and self._text[i + k] == self._text[j + k]:
            k += 1
        return k

    def find(self, s):
        """线性扫描查找模式 s，返回它出现的全部起始下标（升序）。

        模式为空串时返回从 0 到 n 的全部下标各一次。
        """
        if not isinstance(s, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(s)
        hits = []
        if m == 0:
            return list(range(n + 1))
        for i in range(n - m + 1):
            if self._text[i:i + m] == s:
                hits.append(i)
        return hits
