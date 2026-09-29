"""nearbex.sim: 逐字符比较的相似度工具。

CharDiff 是最朴素的实现：把两个字符串按位置逐字符对齐，
数出有多少个位置上的字符不一样，作为差异数。
没有指纹，没有哈希，没有海明距离，也没有任何近似检索能力。
"""


class NearbexError(Exception):
    """nearbex 的异常基类，包内所有自定义异常都从它派生。"""


class CharDiff(object):
    """逐字符比较两个文本的差异数。

    比较口径：
    - 两个字符串从左到右按位置对齐比较；
    - 差异数 = 位置对齐后字符不同的位置个数；
    - 长度不同时，多出来的位置也算作差异。
    """

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def diff_count(self):
        """返回两个文本的差异字符数。"""
        left = self.left
        right = self.right
        shortest = min(len(left), len(right))
        count = 0
        for index in range(shortest):
            if left[index] != right[index]:
                count += 1
        count += abs(len(left) - len(right))
        return count

    def is_same(self):
        """差异数为零即为相同文本。"""
        return self.diff_count() == 0
