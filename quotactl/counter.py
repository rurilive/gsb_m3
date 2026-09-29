"""全局配额计数器，纯标准库。

现有能力（基线）：

- 构造只要一个 limit，上限是总共能放出的量，必须是正整数；
- check(n) 只判断 n 放不放得下，返回布尔值，不改动已用量；
- add(n) 把 n 记到已用量上，放不下时抛 QuotaExceeded 且已用量保持不变；
- limit、used、remaining 三个只读属性，remaining 等于 limit 减 used。

这是一个扁平的全局计数，没有层级，没有预留，也没有借用。
"""


class QuotaError(Exception):
    """配额相关错误的基类。"""


class QuotaExceeded(QuotaError):
    """请求量超出可用额度。"""

    def __init__(self, requested, available):
        super().__init__(
            "requested %d exceeds available %d" % (requested, available)
        )
        self.requested = requested
        self.available = available


def _as_amount(n):
    """把请求量收敛成非负整数，非法入参在读到任何状态之前就拒绝。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("amount must be an int")
    if n < 0:
        raise ValueError("amount must be >= 0")
    return n


class QuotaCounter:
    """单一全局上限的计数器。"""

    def __init__(self, limit):
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an int")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self._limit = limit
        self._used = 0

    @property
    def limit(self):
        """总额度上限。"""
        return self._limit

    @property
    def used(self):
        """已记入的用量。"""
        return self._used

    @property
    def remaining(self):
        """还剩多少额度可用。"""
        return self._limit - self._used

    def check(self, n):
        """判断 n 是否放得下，只读，不改动已用量。"""
        n = _as_amount(n)
        return n <= self._limit - self._used

    def add(self, n):
        """把 n 记入已用量，返回累加后的已用量；放不下时不改动现状。"""
        n = _as_amount(n)
        available = self._limit - self._used
        if n > available:
            raise QuotaExceeded(n, available)
        self._used += n
        return self._used
