"""suflcp 的朴素后缀数组与最长公共前缀实现（改造前的现状）。

现在只有两条最直白的路：

- naive_suffix_array：把文本的每个后缀起点取出来，直接按整段后缀做字典序
  排序，排序键是从起点切到末尾的整段切片，比较时从头一个个字符看。
- naive_lcp_array：相邻后缀的最长公共前缀逐对现算，每对都从头重新扫描。

任意两个后缀之间的最长公共前缀查询、用排名做键的倍增构造、卡萨伊线性
扫描以及稀疏表支撑的区间最小值，都还没有。
"""


class Erro(Exception):
    """本仓库所有异常的基类。"""


class SuffixError(Erro):
    """输入不合法或后缀下标越界时抛出。"""


def _check_text(text):
    if not isinstance(text, str):
        raise SuffixError("text must be a str")


def _check_index(text, idx, name):
    if not isinstance(idx, int) or isinstance(idx, bool):
        raise SuffixError("%s must be an int" % name)
    if idx < 0 or idx > len(text):
        raise SuffixError("%s out of range: %d" % (name, idx))


def naive_suffix_array(text):
    """朴素后缀数组：把所有后缀整段排序，返回起点下标列表。

    排序键就是从起点切到末尾的整段后缀本身，比较时从头逐字符看。
    """
    _check_text(text)
    positions = list(range(len(text)))
    positions.sort(key=lambda start: text[start:])
    return positions


def common_prefix_len(text, a, b):
    """逐字符现算从下标 a、b 出发的两个后缀的最长公共前缀长度。"""
    _check_text(text)
    _check_index(text, a, "a")
    _check_index(text, b, "b")
    limit = min(len(text) - a, len(text) - b)
    i = 0
    while i < limit and text[a + i] == text[b + i]:
        i += 1
    return i


def naive_lcp_array(text):
    """相邻后缀最长公共前缀数组，逐对现算，长度等于文本长度。"""
    sa = naive_suffix_array(text)
    n = len(text)
    out = []
    for i in range(n):
        if i + 1 < n:
            out.append(common_prefix_len(text, sa[i], sa[i + 1]))
        else:
            out.append(0)
    return out


class SuffixArray:
    """把朴素结果封成一个门面，供后续改造替换内部实现。"""

    def __init__(self, text):
        _check_text(text)
        self._text = text
        self._sa = naive_suffix_array(text)
        self._lcp = naive_lcp_array(text)

    @property
    def text(self):
        return self._text

    def __len__(self):
        return len(self._text)

    def suffix_array(self):
        """后缀数组，返回起点下标列表。"""
        return list(self._sa)

    def rank(self):
        """排名的逆表：rank[i] 是后缀 i 在后缀数组里的位次。"""
        inv = [0] * len(self._sa)
        for pos, start in enumerate(self._sa):
            inv[start] = pos
        return inv

    def lcp_array(self):
        """相邻后缀最长公共前缀数组。"""
        return list(self._lcp)

    def lcp(self, i, j):
        """任意两个后缀的最长公共前缀，当前逐字符现算。"""
        return common_prefix_len(self._text, i, j)
