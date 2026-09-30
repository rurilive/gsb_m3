"""hashx 的朴素实现（改造前基线）。

对字符串只做最直白的处理：判断两个子串是否相等就逐字符比；求最长重复子串、
最长回文子串、两串最长公共子串都是先枚举出所有子串对，再逐个字符比较。
功能正确，规模一大就是立方或平方级，也没有任何哈希与幂表可用。
"""


class HashxError(Exception):
    """本库所有异常的基类。"""


class InvalidInputError(HashxError, ValueError):
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


def _sub_eq(text_a, start_a, end_a, text_b, start_b, end_b):
    """朴素子串判等：长度不等直接否，否则逐字符比。"""
    if end_a - start_a != end_b - start_b:
        return False
    for offset in range(end_a - start_a):
        if text_a[start_a + offset] != text_b[start_b + offset]:
            return False
    return True


class StringTools:
    """字符串子串判等与常见子串问题的朴素实现。

    equal(a_start, a_end, b_start, b_end)：判断同一文本中两个子串是否相等。
    longest_repeat()：最长重复子串（至少出现两次），取最早出现的一例。
    longest_palindrome()：最长回文子串，取最早出现的一例。
    longest_common_substring(other)：与另一文本的最长公共子串，取最早出现的一例。
    """

    def __init__(self, text=""):
        self._text = _check_text(text)

    def text(self):
        return self._text

    def equal(self, a_start, a_end, b_start, b_end):
        n = len(self._text)
        _check_range(a_start, a_end, n)
        _check_range(b_start, b_end, n)
        return _sub_eq(self._text, a_start, a_end, self._text, b_start, b_end)

    def _all_substrings(self):
        """枚举全部子串，按 (起点, 终点) 升序。"""
        n = len(self._text)
        for start in range(n):
            for end in range(start + 1, n + 1):
                yield start, end

    def longest_repeat(self):
        """最长重复子串：枚举子串对再逐字符比，长的一对先试。"""
        best = ""
        subs = list(self._all_substrings())
        subs.sort(key=lambda pair: (pair[0] - pair[1], pair[0]))
        for start_a, end_a in subs:
            length = end_a - start_a
            if length <= len(best):
                continue
            for start_b, end_b in self._all_substrings():
                if start_b == start_a and end_b == end_a:
                    continue
                if _sub_eq(self._text, start_a, end_a, self._text, start_b, end_b):
                    best = self._text[start_a:end_a]
                    break
        return best

    def longest_palindrome(self):
        """最长回文子串：枚举全部子串，逐个判断是否回文。"""
        best = ""
        for start, end in self._all_substrings():
            if end - start <= len(best):
                continue
            chunk = self._text[start:end]
            if chunk == chunk[::-1]:
                best = chunk
        return best

    def longest_common_substring(self, other):
        """与另一文本的最长公共子串：枚举两边的子串对再逐字符比。"""
        other = _check_text(other)
        best = ""
        for a_start, a_end in self._all_substrings():
            length = a_end - a_start
            if length <= len(best):
                continue
            m = len(other)
            for b_start in range(m):
                b_end = b_start + length
                if b_end > m:
                    break
                if _sub_eq(self._text, a_start, a_end, other, b_start, b_end):
                    best = self._text[a_start:a_end]
                    break
        return best
