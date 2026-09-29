"""digitx.count：改造前基线的朴素数位计数实现。

所有计数都从一到上界逐个整数地枚举，对每个整数翻成十进制串再逐位检查，
因此计算量随上界线性增长，上界一大就明显变慢。这里没有数位动态规划，
也没有任何与位数相关、与上界大小无关的状态结构。
"""


class DigitError(Exception):
    """数位计数相关异常的共同基类。"""


class InvalidBoundError(DigitError):
    """上界或数字取值不合法时抛出。"""


class InvalidDigitError(DigitError):
    """被查询的数字不是十进制数码时抛出。"""


class BruteDigits:
    """朴素数位计数：从一到上界逐个整数枚举并统计。

    实例不持有跨调用状态，每一次计数都在本地重新累加，固定输入必得固定结果。
    """

    def _check_bound(self, n):
        if not isinstance(n, int) or isinstance(n, bool):
            raise InvalidBoundError("上界必须是整数")
        if n < 0:
            raise InvalidBoundError("上界必须非负")
        return n

    def _check_digit(self, d):
        if not isinstance(d, int) or isinstance(d, bool):
            raise InvalidDigitError("数字必须是整数")
        if d < 0 or d > 9:
            raise InvalidDigitError("数字必须落在零到九之间")
        return d

    def _check_divisor(self, m):
        if not isinstance(m, int) or isinstance(m, bool):
            raise DigitError("除数必须是整数")
        if m <= 0:
            raise DigitError("除数必须为正")
        return m

    def count_with_digit(self, n, d):
        """一到 n 里，十进制表示含数字 d 的整数个数。

        前导零不计入，因此数字零只统计它真正出现在数位上的那些整数。
        """
        self._check_bound(n)
        self._check_digit(d)
        target = str(d)
        total = 0
        for i in range(1, n + 1):
            if target in str(i):
                total += 1
        return total

    def sum_of_digits(self, n):
        """一到 n 里，全部整数的各个十进制位数字之和。"""
        self._check_bound(n)
        total = 0
        for i in range(1, n + 1):
            for ch in str(i):
                total += int(ch)
        return total

    def count_less_than(self, n, x):
        """一到 n 里，数值不大于给定上界 x 的整数个数。"""
        self._check_bound(n)
        if not isinstance(x, int) or isinstance(x, bool):
            raise InvalidBoundError("比较值必须是整数")
        if x < 0:
            raise InvalidBoundError("比较值必须非负")
        total = 0
        for i in range(1, n + 1):
            if i <= x:
                total += 1
        return total

    def count_divisible(self, n, m):
        """一到 n 里，能被 m 整除的整数个数。"""
        self._check_bound(n)
        self._check_divisor(m)
        total = 0
        for i in range(1, n + 1):
            if i % m == 0:
                total += 1
        return total
