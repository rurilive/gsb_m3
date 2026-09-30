"""朴素子串工具。

当前实现只做几件事的朴素版本：把全部子串枚举进集合去重，判断某个
模式是不是子串用逐个起始位置的朴素匹配，不同子串个数直接数集合大小，
出现次数用线性扫描计数。文本一长，这些路径全是平方级时间加大量内存。
"""


class Erro(Exception):
    """子串工具里所有错误的基类。"""


class SubstringError(Erro):
    """子串操作出错。"""


class IndexError_(Erro):
    """下标越界或下标类型非法。"""


class NaiveSubstrings:
    """在一段文本上做朴素子串操作的薄封装。

    文本一经构造即不可变；所有方法都是只读查询。朴素实现会把全部
    子串枚举进内存，子串一多就平方级时间加大量内存。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("text 必须是字符串")
        self._text = text

    def __repr__(self):
        return f"<NaiveSubstrings {len(self._text)} chars>"

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

    def all_substrings(self):
        """枚举全部子串（含重复），按起点升序、同起点按终点升序。"""
        n = len(self._text)
        out = []
        for i in range(n):
            for j in range(i + 1, n + 1):
                out.append(self._text[i:j])
        return out

    def distinct_substrings(self):
        """把全部子串枚举进集合去重后返回。"""
        return set(self.all_substrings())

    def count_distinct_substrings(self):
        """不同子串个数：直接数集合大小。"""
        return len(self.distinct_substrings())

    def is_substring(self, pattern):
        """判断 pattern 是不是子串：逐个起始位置朴素匹配。"""
        if not isinstance(pattern, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(pattern)
        if m == 0:
            return True
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                return True
        return False

    def count_occurrences(self, pattern):
        """统计 pattern 出现次数：对每个起点做线性扫描比对。"""
        if not isinstance(pattern, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(pattern)
        if m == 0:
            return 0
        cnt = 0
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                cnt += 1
        return cnt

    def count_substrings_by_length(self):
        """不同子串按长度聚合：长度到数量的映射。"""
        by_len = {}
        for s in self.distinct_substrings():
            by_len[len(s)] = by_len.get(len(s), 0) + 1
        return by_len

    def distinct_substring_lengths(self):
        """全部不同子串的长度去重后升序返回。"""
        return sorted({len(s) for s in self.distinct_substrings()})
