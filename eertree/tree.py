"""朴素回文子串工具：内部只持一段文本，全部事实靠当场枚举子串算出来。

BrutePalTree 把文本存在自己身上，凡是回文相关的问题都从枚举子串现算：
判断某个子串是否回文，是从两端往中间逐字符镜像比对；枚举全部回文子串，
是把所有下标区间过一遍再挑出回文的收进列表，同一个回文出现几次就收几
次，不去重；统计以某个位置结尾的回文子串个数，是把以该位置结尾的每个
区间都判一次；判断某个回文是否作为子串出现，又把整段文本扫一遍。全程
没有任何预处理，结论算完即弃、从不留存复用，代价随文本长度的平方增长。

回文树（回文自动机，带失配链与长度零、长度负一两个根）以及本质不同回
文统计、逐位置增量、各回文出现次数、最长回文后缀、按长度分布等见任务
描述。
"""


class Erro(Exception):
    """本模块所有异常的基类，便于调用方一把兜住。"""


class IllegalArgument(Erro):
    """参数类型或取值非法。"""


class NotASubstring(Erro):
    """给出的串并不是当前文本的子串。"""


class IndexOutOfRange(Erro):
    """位置下标越界。"""


class BrutePalTree(object):
    """朴素回文子串结构，内部持有单个字符串，一切现算。"""

    def __init__(self, text):
        if not isinstance(text, str):
            raise IllegalArgument("文本必须是字符串")
        self._text = text

    @property
    def text(self):
        return self._text

    def __len__(self):
        return len(self._text)

    def _check_index(self, i):
        if not isinstance(i, int) or isinstance(i, bool):
            raise IllegalArgument("下标必须是整数")
        if i < 0 or i >= len(self._text):
            raise IndexOutOfRange("下标越界: %r" % (i,))

    def _is_pal_slice(self, start, end):
        """判断 [start, end) 这段区间是否回文。"""
        left = start
        right = end - 1
        while left < right:
            if self._text[left] != self._text[right]:
                return False
            left += 1
            right -= 1
        return True

    @staticmethod
    def _is_palindrome(s):
        """单纯的镜像判断，不涉及文本归属。"""
        left = 0
        right = len(s) - 1
        while left < right:
            if s[left] != s[right]:
                return False
            left += 1
            right -= 1
        return True

    def is_pal(self, s):
        """判断给定子串是否回文；不是当前文本的子串则报错。"""
        if not isinstance(s, str):
            raise IllegalArgument("待判断的必须是字符串")
        if s == "":
            raise IllegalArgument("空串不作为子串判断")
        if s not in self._text:
            raise NotASubstring("不是当前文本的子串: %r" % (s,))
        return self._is_palindrome(s)

    def palindromic_substrings(self):
        """枚举全部子串并挑出回文，按起点、再由短到长收集成列表。

        同一个回文在文本里出现几次就收几次，不做去重。
        """
        result = []
        n = len(self._text)
        for start in range(n):
            for end in range(start + 1, n + 1):
                if self._is_pal_slice(start, end):
                    result.append(self._text[start:end])
        return result

    def distinct_pal_count(self):
        """本质不同回文子串个数：暴力枚举后按集合去重再数。"""
        seen = set()
        for s in self.palindromic_substrings():
            seen.add(s)
        return len(seen)

    def pal_count_by_end(self, i):
        """统计以位置 i 结尾（含单字符本身）的回文子串个数。"""
        self._check_index(i)
        count = 0
        for start in range(i + 1):
            if self._is_pal_slice(start, i + 1):
                count += 1
        return count

    def longest_pal_suffix(self, i):
        """以位置 i 结尾的最长回文子串长度；位置 i 处必有单字符回文。"""
        self._check_index(i)
        best = 0
        for start in range(i + 1):
            if self._is_pal_slice(start, i + 1):
                best = max(best, i + 1 - start)
        return best

    def contains_pal(self, x):
        """判断给定回文是否作为子串出现；非回文直接报错。"""
        if not isinstance(x, str):
            raise IllegalArgument("待判断的必须是字符串")
        if x == "":
            raise IllegalArgument("空串不作为回文判断")
        if not self._is_palindrome(x):
            raise IllegalArgument("给定串本身不是回文: %r" % (x,))
        return x in self._text
