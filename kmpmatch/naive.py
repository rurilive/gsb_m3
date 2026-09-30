"""kmpmatch 的朴素字符串匹配工具（改造前的现状）。

现在只有一条最直白的路：模式在文本里出现的位置，对文本的每个起点
逐位拿去和模式对齐比较，能对上就记下起点，再错开一位重来；最长公
共前后缀长度数组，对每个位置从大到小逐个候选长度重新逐位比较；最
小整周期与是否整周期，对每个候选周期长度逐位试过去；多模式匹配则是
把每个模式各自扫一遍文本。结果都对，但失配之后前面比出来的信息一点
没被接着用，规模一大比较次数就随串长乘积往上蹿。线性做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class TextError(Erro):
    """文本、模式或模式集合的非法输入。"""


def _check_text(text):
    """文本必须是字符串，允许为空串。"""
    if not isinstance(text, str):
        raise TextError("text must be a str")
    return text


def _check_pattern(pattern):
    """模式必须是字符串，且不得为空串。"""
    if not isinstance(pattern, str):
        raise TextError("pattern must be a str")
    if pattern == "":
        raise TextError("pattern must not be empty")
    return pattern


def _positions_naive(pattern, text):
    """朴素查找：每个起点逐位对齐比较，返回升序起点列表。

    模式为空或长于文本时没有任何起点，直接返回空列表。
    """
    positions = []
    n = len(text)
    m = len(pattern)
    if m == 0 or m > n:
        return positions
    for start in range(n - m + 1):
        k = 0
        while k < m and text[start + k] == pattern[k]:
            k += 1
        if k == m:
            positions.append(start)
    return positions


def occurrences(pattern, text):
    """模式在文本里出现的全部起点，升序，允许重叠。"""
    _check_pattern(pattern)
    _check_text(text)
    return _positions_naive(pattern, text)


def count(pattern, text):
    """模式在文本里出现的次数，允许重叠。"""
    return len(occurrences(pattern, text))


def occurrences_many(patterns, text):
    """朴素多模式：逐个模式各自扫一遍文本。

    patterns 是一个由非空字符串组成的列表或元组，返回一个字典，键是模式
    （按首次出现的顺序去重），值是它在文本里出现的全部起点，升序且允许重叠。
    """
    _check_text(text)
    if not isinstance(patterns, (list, tuple)):
        raise TextError("patterns must be a list or tuple")
    result = {}
    for pattern in patterns:
        _check_pattern(pattern)
        result[pattern] = _positions_naive(pattern, text)
    return result


def prefix_naive(pattern):
    """朴素最长公共前后缀长度数组，逐个候选长度重新逐位比较。

    pi[i] 是 pattern 的前 i 加 1 个字符这一段里，最长的既是真前缀又是真后缀
    的长度；pi[0] 记为零。空串得到空列表。
    """
    _check_text(pattern)
    n = len(pattern)
    pi = [0] * n
    for i in range(n):
        for k in range(i, 0, -1):
            ok = True
            for j in range(k):
                if pattern[j] != pattern[i - k + 1 + j]:
                    ok = False
                    break
            if ok:
                pi[i] = k
                break
    return pi


def min_period(text):
    """最小整周期长度：使得文本恰由某个前缀重复整数次的最小长度。

    空串返回零；找不到更短周期时返回文本长度本身。
    """
    _check_text(text)
    n = len(text)
    if n == 0:
        return 0
    for p in range(1, n + 1):
        if n % p:
            continue
        ok = True
        for i in range(p, n):
            if text[i] != text[i - p]:
                ok = False
                break
        if ok:
            return p
    return n


def is_periodic(text):
    """文本是否存在比自身更短的整周期，即是否由某个真前缀重复而成。"""
    _check_text(text)
    n = len(text)
    if n == 0:
        return False
    return min_period(text) < n


class TextTools:
    """绑定一段文本的匹配工具，只有逐位直接比较这一条路。

    每个方法都按最直白的循环完成，并把逐字符比较的次数累计进计数器，
    供与线性做法对照规模。文本在构造时校验并固定。
    """

    def __init__(self, text):
        self._text = _check_text(text)
        self._compare_count = 0

    def text(self):
        """返回绑定的文本。"""
        return self._text

    def reset_compare_count(self):
        """把逐字符比较计数清零。"""
        self._compare_count = 0

    def compare_count(self):
        """自上次清零以来累计比较了多少个字符位置。"""
        return self._compare_count

    def occurrences(self, pattern):
        """朴素查找：每个起点逐位对齐，返回升序起点列表并累计比较次数。"""
        _check_pattern(pattern)
        text = self._text
        positions = []
        n = len(text)
        m = len(pattern)
        if m > n:
            return positions
        for start in range(n - m + 1):
            k = 0
            while k < m:
                self._compare_count += 1
                if text[start + k] != pattern[k]:
                    break
                k += 1
            if k == m:
                positions.append(start)
        return positions

    def count(self, pattern):
        """模式在绑定文本里出现的次数，允许重叠。"""
        return len(self.occurrences(pattern))

    def occurrences_many(self, patterns):
        """朴素多模式：逐个模式各自扫一遍绑定文本并累计比较次数。"""
        if not isinstance(patterns, (list, tuple)):
            raise TextError("patterns must be a list or tuple")
        result = {}
        for pattern in patterns:
            result[pattern] = self.occurrences(pattern)
        return result

    def prefix_naive(self, pattern):
        """朴素最长公共前后缀长度数组，逐个候选长度比较并累计次数。"""
        _check_text(pattern)
        n = len(pattern)
        pi = [0] * n
        for i in range(n):
            for k in range(i, 0, -1):
                ok = True
                for j in range(k):
                    self._compare_count += 1
                    if pattern[j] != pattern[i - k + 1 + j]:
                        ok = False
                        break
                if ok:
                    pi[i] = k
                    break
        return pi

    def min_period(self):
        """最小整周期长度，逐位试并累计比较次数。"""
        text = self._text
        n = len(text)
        if n == 0:
            return 0
        for p in range(1, n + 1):
            if n % p:
                continue
            ok = True
            for i in range(p, n):
                self._compare_count += 1
                if text[i] != text[i - p]:
                    ok = False
                    break
            if ok:
                return p
        return n

    def is_periodic(self):
        """文本是否存在比自身更短的整周期。"""
        n = len(self._text)
        if n == 0:
            return False
        return self.min_period() < n
