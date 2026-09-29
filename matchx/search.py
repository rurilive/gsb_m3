"""matchx.search：朴素字符串查找的基线实现（改造前）。

本模块只提供最朴素的双层逐位比对：从文本的每个位置起，把模式逐字符地与
文本对齐比较，命中即记录，未命中就整体右移一位重来。文本一长，代价就退化
成平方级；多模式只能一个个模式分别扫。

约定：
- find 返回首次出现的下标，未命中返回负一；
- find_all 返回全部出现的起始下标（含重叠），按升序；
- has 返回是否出现；
- count 返回出现次数；
- 空模式视为非法，抛 InvalidPatternError（它是 ValueError 与 MatchError 的子类）。
"""


class MatchError(Exception):
    """matchx 所有匹配相关异常的基类。"""


class InvalidPatternError(MatchError, ValueError):
    """模式非法（例如空模式）时抛出。

    同时继承 MatchError 与 ValueError：既满足改造后统一继承基类的口径，
    又保持改造前「空模式抛 ValueError」的既有行为。
    """


class NaiveSearch:
    """朴素查找器：双层逐位比对，逐位把文本与模式比较。

    每次调用都会重置 self.comparisons，记录本次调用发生的字符比较次数，
    便于观察平方级退化。
    """

    def __init__(self):
        self.comparisons = 0

    # -- 内部工具 --------------------------------------------------------

    @staticmethod
    def _validate(text, pat):
        if not isinstance(text, str):
            raise InvalidPatternError("text 必须是字符串")
        if not isinstance(pat, str):
            raise InvalidPatternError("pattern 必须是字符串")
        if pat == "":
            raise InvalidPatternError("空模式非法")

    def _match_at(self, text, pat, start):
        """从 start 起逐位比对，返回是否命中（并累计比较次数）。"""
        m = len(pat)
        for j in range(m):
            self.comparisons += 1
            if text[start + j] != pat[j]:
                return False
        return True

    # -- 公开能力 --------------------------------------------------------

    def find(self, text, pat):
        """返回 pat 在 text 中首次出现的下标，未命中返回负一。"""
        self._validate(text, pat)
        self.comparisons = 0
        n, m = len(text), len(pat)
        for start in range(n - m + 1):
            if self._match_at(text, pat, start):
                return start
        return -1

    def find_all(self, text, pat):
        """返回 pat 在 text 中全部出现的起始下标（含重叠），升序。"""
        self._validate(text, pat)
        self.comparisons = 0
        n, m = len(text), len(pat)
        hits = []
        for start in range(n - m + 1):
            if self._match_at(text, pat, start):
                hits.append(start)
        return hits

    def has(self, text, pat):
        """返回 pat 是否在 text 中出现过。"""
        return self.find(text, pat) != -1

    def count(self, text, pat):
        """返回 pat 在 text 中出现的次数（含重叠）。"""
        return len(self.find_all(text, pat))


# -- 便捷函数：每次调用新建实例，不依赖模块级可变状态 ----------------------

def find(text, pat):
    return NaiveSearch().find(text, pat)


def find_all(text, pat):
    return NaiveSearch().find_all(text, pat)


def has(text, pat):
    return NaiveSearch().has(text, pat)


def count(text, pat):
    return NaiveSearch().count(text, pat)
