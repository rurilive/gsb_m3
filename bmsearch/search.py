"""bmsearch 的朴素实现（改造前基线）。

对文本里的每一个对齐位置，从前往后逐字符与模式比对，一旦失配就把窗口整体右移
一位，从文本的下一个起点重新对齐比较。找出现位置、统计出现次数、判断是否出现，
全都走这一条逐位对齐的路子：无论模式与文本长什么样，位移量恒为一，没有任何根据
坏字符或已匹配后缀跳过一段的机制。功能正确，最坏情形是平方量级，长文本上比较
次数与对齐次数都随长度线性以上增长。
"""


class SearchError(Exception):
    """本库所有异常的基类。"""


class InvalidInputError(SearchError, ValueError):
    """违反输入口径时抛出（模式或文本非字符串、查找用空模式等）。"""


def _check_text(value, name):
    """文本校验：必须是字符串。"""
    if not isinstance(value, str):
        raise InvalidInputError(f"{name}必须是字符串")
    return value


def _naive_search(pattern, text):
    """朴素查找：对每个对齐位置逐字符比对，返回 (位置列表, 逐次匹配信息, 比较次数, 位移次数)。

    位置列表为全部出现位置的起始下标，升序，允许互相重叠。逐次匹配信息与位置列表
    一一对应，每条给出该次匹配的起始下标、自上一次匹配对齐以来窗口右移的次数、以及
    确认这一次匹配所花费的字符比较次数。比较次数为本次查找全部对齐的字符比较总和，
    位移次数为窗口右移的总次数（最后一次对齐之后不再右移）。
    """
    lp = len(pattern)
    lt = len(text)
    hits = []
    per_match = []
    total_comp = 0
    total_jumps = 0
    prev_hit = 0
    start = 0
    while start <= lt - lp:
        comp = 0
        matched = True
        for j in range(lp):
            comp += 1
            if text[start + j] != pattern[j]:
                matched = False
                break
        total_comp += comp
        if matched:
            hits.append(start)
            per_match.append({"start": start, "jumps": start - prev_hit, "comparisons": comp})
            prev_hit = start
        if start < lt - lp:
            total_jumps += 1
        start += 1
    return hits, per_match, total_comp, total_jumps


class BmSearch:
    """字符串查找的朴素实现。

    find_occurrences(text)：模式在文本中全部出现位置的起始下标，升序，允许重叠。
    count_occurrences(text)：出现位置个数。
    contains(text)：是否至少出现一次。
    match_steps()：最近一次查找的逐次匹配信息，每条含起始下标、位移次数、比较次数。
    search_steps()：最近一次查找的字符比较总次数。
    search_jumps()：最近一次查找的窗口位移总次数。
    naive_comparisons(text)：对给定文本走一遍朴素查找，返回其字符比较总次数。
    """

    def __init__(self, pattern=""):
        self._pattern = _check_text(pattern, "模式")
        self._hits = []
        self._per_match = []
        self._steps = 0
        self._jumps = 0

    def pattern(self):
        return self._pattern

    def find_occurrences(self, text):
        _check_text(text, "文本")
        if not self._pattern:
            raise InvalidInputError("空模式不允许查找")
        hits, per_match, comp, jumps = _naive_search(self._pattern, text)
        self._hits = hits
        self._per_match = per_match
        self._steps = comp
        self._jumps = jumps
        return list(hits)

    def count_occurrences(self, text):
        return len(self.find_occurrences(text))

    def contains(self, text):
        return len(self.find_occurrences(text)) > 0

    def match_steps(self):
        return [dict(entry) for entry in self._per_match]

    def search_steps(self):
        return self._steps

    def search_jumps(self):
        return self._jumps

    def naive_comparisons(self, text):
        _check_text(text, "文本")
        if not self._pattern:
            raise InvalidInputError("空模式不允许查找")
        _, _, comp, _ = _naive_search(self._pattern, text)
        return comp
