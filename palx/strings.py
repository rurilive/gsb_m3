"""palx 的朴素实现（改造前基线）。

对字符串只做最直白的处理：判断一个子串是否回文，就把该子串切片再反转后整体
比较；求最长回文子串，就对每个中心向两边逐字符扩展，记录扩展了多少次；统计
回文子串个数、求最小回文划分与回文划分计数，都是先把全部子串枚举出来，再逐个
判断是否回文。功能正确，规模一大就是平方或立方级，也没有任何回文半径或线性
扫描可用。
"""


class PalxError(Exception):
    """本库所有异常的基类。"""


class InvalidInputError(PalxError, ValueError):
    """违反输入口径时抛出（非字符串、下标越界、区间反向等）。"""


def _check_text(text):
    """文本校验：必须是字符串。"""
    if not isinstance(text, str):
        raise InvalidInputError("输入必须是字符串")
    return text


def _check_range(start, end, length):
    """区间校验：下标为整数，且 0 <= start <= end <= length。"""
    if isinstance(start, bool) or not isinstance(start, int):
        raise InvalidInputError("区间下标必须是整数")
    if isinstance(end, bool) or not isinstance(end, int):
        raise InvalidInputError("区间下标必须是整数")
    if start < 0 or end < start or end > length:
        raise InvalidInputError("区间越界或反向")
    return start, end


def _is_palindrome(chunk):
    """朴素回文判断：把切片反转后与原切片整体比较。"""
    return chunk == chunk[::-1]


class PalindromeTools:
    """回文子串相关问题的朴素实现。

    is_palindrome(start, end)：判断文本中 [start, end) 子串是否回文。
    longest_palindrome()：最长回文子串，取最早出现的一例，逐中心向两边扩展。
    count_palindromes()：统计回文子串（含重复出现）的总个数。
    min_palindrome_cut()：最小回文划分的段数。
    count_palindrome_cut()：回文划分的方案总数。
    expand_steps()：最近一次求最长回文时中心扩展的比较次数。
    """

    def __init__(self, text=""):
        self._text = _check_text(text)
        self._steps = 0

    def text(self):
        return self._text

    def _all_substrings(self):
        """枚举全部子串，按 (起点, 终点) 升序。"""
        n = len(self._text)
        for start in range(n):
            for end in range(start + 1, n + 1):
                yield start, end

    def is_palindrome(self, start, end):
        n = len(self._text)
        _check_range(start, end, n)
        return _is_palindrome(self._text[start:end])

    def longest_palindrome(self):
        """最长回文子串：对每个奇中心与偶中心向两边逐字符扩展。

        扩展时把每一对成功匹配的字符记一次比较，奇中心与偶中心分开各扫一遍，
        半径取到不能再扩为止；同长时保留最早出现的一例。
        """
        n = len(self._text)
        best = ""
        steps = 0

        for center in range(n):
            left = center
            right = center
            while left >= 0 and right < n and self._text[left] == self._text[right]:
                steps += 1
                left -= 1
                right += 1
            length = right - left - 1
            if length > len(best):
                best = self._text[left + 1:right]

        for center in range(n - 1):
            left = center
            right = center + 1
            while left >= 0 and right < n and self._text[left] == self._text[right]:
                steps += 1
                left -= 1
                right += 1
            length = right - left - 1
            if length > len(best):
                best = self._text[left + 1:right]

        self._steps = steps
        return best

    def count_palindromes(self):
        """统计回文子串个数：枚举全部子串，逐个切片反转判断。"""
        total = 0
        for start, end in self._all_substrings():
            if _is_palindrome(self._text[start:end]):
                total += 1
        return total

    def min_palindrome_cut(self):
        """最小回文划分段数：对每个前缀枚举最后一段回文，取最少段数。"""
        n = len(self._text)
        best = [0] * (n + 1)
        for end in range(1, n + 1):
            value = end
            for start in range(end):
                if _is_palindrome(self._text[start:end]):
                    if best[start] + 1 < value:
                        value = best[start] + 1
            best[end] = value
        return best[n]

    def count_palindrome_cut(self):
        """回文划分方案总数：对每个前缀枚举最后一段回文，累加方案数。"""
        n = len(self._text)
        ways = [0] * (n + 1)
        ways[0] = 1
        for end in range(1, n + 1):
            total = 0
            for start in range(end):
                if _is_palindrome(self._text[start:end]):
                    total += ways[start]
            ways[end] = total
        return ways[n]

    def expand_steps(self):
        """最近一次求最长回文时中心扩展的比较次数。"""
        return self._steps
