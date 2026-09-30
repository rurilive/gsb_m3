"""zstr 的朴素字符串前后缀工具（改造前的现状）。

现在只有一条路：Z 数组对每个位置从头逐字符比较，出现位置对每个
起点逐位对齐比较，整周期与最小周期靠逐位试。结果都对，但每个起点
都要重新比较一遍，规模一大就成平方量级。线性做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class TextError(Erro):
    """文本或模式的非法输入。"""


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


def z_array(text):
    """朴素 Z 数组：每个后缀与原串的最长公共前缀长度，逐位比较。

    z[0] 按惯例记为零（原串与自身不做自身匹配）。返回与文本等长的列表，
    下标 i 处是 text[i:] 与 text 的最长公共前缀长度。
    """
    _check_text(text)
    n = len(text)
    z = [0] * n
    for i in range(1, n):
        while i + z[i] < n and text[z[i]] == text[i + z[i]]:
            z[i] += 1
    return z


def _positions_naive(pattern, text):
    """朴素查找：每个起点逐位对齐比较，返回升序起点列表。"""
    positions = []
    n = len(text)
    m = len(pattern)
    if m == 0 or m > n:
        return positions
    for start in range(n - m + 1):
        ok = True
        for k in range(m):
            if text[start + k] != pattern[k]:
                ok = False
                break
        if ok:
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
    n = len(text)
    if n == 0:
        return False
    return min_period(text) < n


class TextTools:
    """绑定一段文本的前后缀工具，只有逐位直接比较这一条路。

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

    def z_array(self):
        """朴素 Z 数组，逐位比较并累计比较次数。"""
        text = self._text
        n = len(text)
        z = [0] * n
        for i in range(1, n):
            while i + z[i] < n:
                self._compare_count += 1
                if text[z[i]] != text[i + z[i]]:
                    break
                z[i] += 1
        return z

    def occurrences(self, pattern):
        """朴素查找：每个起点逐位对齐，返回升序起点列表并累计比较次数。"""
        _check_pattern(pattern)
        text = self._text
        positions = []
        n = len(text)
        m = len(pattern)
        if m == 0 or m > n:
            return positions
        for start in range(n - m + 1):
            ok = True
            for k in range(m):
                self._compare_count += 1
                if text[start + k] != pattern[k]:
                    ok = False
                    break
            if ok:
                positions.append(start)
        return positions

    def count(self, pattern):
        """模式在绑定文本里出现的次数，允许重叠。"""
        return len(self.occurrences(pattern))

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
