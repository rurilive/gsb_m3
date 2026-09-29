"""multimatch 当前实现：最朴素的逐模式子串扫描。

现在只有一种能力：把若干个模式逐个拿去在文本里做朴素子串查找。
每个模式单独跑一遍查找，模式之间不共享任何结构，也没有前缀共享、
没有失配指针、没有一次遍历。文本因此会被反复扫描多遍，全都留在
这个模块里。
"""

from collections import namedtuple

# 一次命中：命中了哪个模式，以及它在文本里的起止下标（左闭右开）。
Match = namedtuple("Match", ["pattern", "start", "end"])


class MultiMatchError(Exception):
    """multimatch 所有相关异常的基类。"""


class InvalidPatternError(MultiMatchError):
    """模式集不合法，例如模式不是字符串，或者模式为空串。"""


def _check_patterns(patterns):
    """把模式集规整成一个按注册顺序排列的元组。

    模式必须是字符串；空串在朴素实现里没有独立的查找口径，一律判为非法。
    允许空的模式集，此时匹配器不命中任何东西。
    """
    checked = []
    for pattern in patterns:
        if not isinstance(pattern, str):
            raise InvalidPatternError("模式必须是字符串: %r" % (pattern,))
        if pattern == "":
            raise InvalidPatternError("模式不能是空串")
        checked.append(pattern)
    return tuple(checked)


def _find_naive(text, pattern):
    """在文本里做朴素子串查找，返回全部起始下标，按下标升序。

    逐个候选位置逐字符比较，允许出现重叠，比如模式是 aa、文本是 aaa 时
    会返回 0 和 1 两个起始位置。
    """
    starts = []
    n = len(text)
    m = len(pattern)
    limit = n - m
    for start in range(limit + 1):
        if text[start:start + m] == pattern:
            starts.append(start)
    return starts


class EachPattern:
    """逐模式扫描的朴素匹配器。

    内部只保留一份按注册顺序排列的模式元组。每次查找都对每个模式
    各自跑一遍朴素子串查找，再把结果按模式注册顺序拼起来。
    没有前缀树，没有失配指针，也没有共享前缀或一次遍历的概念。
    """

    def __init__(self, patterns=()):
        self._patterns = _check_patterns(patterns)

    def patterns(self):
        """返回全部模式，按注册顺序。"""
        return list(self._patterns)

    def find(self, text):
        """逐模式扫描文本，返回全部命中。

        结果按模式注册顺序分组，同一模式内部按下标升序；重叠出现都会
        被报出。文本必须是字符串。
        """
        if not isinstance(text, str):
            raise InvalidPatternError("文本必须是字符串: %r" % (text,))
        matches = []
        for pattern in self._patterns:
            for start in _find_naive(text, pattern):
                matches.append(Match(pattern, start, start + len(pattern)))
        return matches
