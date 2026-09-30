"""digitcount.counter：改造前基线的朴素区间数位计数实现。

四类计数都靠在闭区间 [lo, hi] 上逐个整数地枚举完成：把每个整数翻成十进制
串，逐位分解后再逐条判定，区间宽度一大就线性退化。这里没有任何按位推进的
数位动态规划，也没有跨整数复用的状态结构，走过的整数个数就是它的全部工作量。
"""


class DigitCountError(Exception):
    """数位计数相关异常的共同基类。"""


class InvalidBoundError(DigitCountError):
    """区间端点取值不合法时抛出。"""


class InvalidDigitError(DigitCountError):
    """被查询的数字不是十进制数码时抛出。"""


class InvalidModError(DigitCountError):
    """模数不是正整数时抛出。"""


class NaiveDigitCounter:
    """朴素区间数位计数：把 [lo, hi] 里每个整数翻成十进制串再逐位判定。

    实例不持有跨调用状态，每一次计数都在本地重新累加，固定输入必得固定结果，
    同一实例反复调用也不会残留上一轮的痕迹。
    """

    def _check_bounds(self, lo, hi):
        for name, value in (("下界", lo), ("上界", hi)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise InvalidBoundError(name + "必须是整数")
            if value < 0:
                raise InvalidBoundError(name + "必须非负")
        return lo, hi

    def _check_digit(self, d):
        if not isinstance(d, int) or isinstance(d, bool):
            raise InvalidDigitError("数字必须是整数")
        if d < 0 or d > 9:
            raise InvalidDigitError("数字必须落在零到九之间")
        return d

    def _check_mod(self, m):
        if not isinstance(m, int) or isinstance(m, bool):
            raise InvalidModError("模数必须是整数")
        if m <= 0:
            raise InvalidModError("模数必须为正")
        return m

    @staticmethod
    def _digits(n):
        """把整数 n 拆成各十进制位上的数字，最高位在前，前导零不出现。"""
        out = []
        if n == 0:
            return [0]
        while n > 0:
            out.append(n % 10)
            n //= 10
        out.reverse()
        return out

    def count_sum_mod(self, lo, hi, m, rem):
        """[lo, hi] 里各位数字之和对 m 取余等于 rem 的整数个数。

        数字零与退化成单点的区间都按字面口径处理，前导零不计入数位。
        """
        lo, hi = self._check_bounds(lo, hi)
        m = self._check_mod(m)
        if not isinstance(rem, int) or isinstance(rem, bool):
            raise InvalidModError("余数必须是整数")
        if rem < 0 or rem >= m:
            raise InvalidModError("余数必须落在零到模数减一之间")
        if lo > hi:
            return 0
        total = 0
        for n in range(lo, hi + 1):
            if sum(self._digits(n)) % m == rem:
                total += 1
        return total

    def count_contains(self, lo, hi, d):
        """[lo, hi] 里十进制表示含数字 d 的整数个数。

        前导零不出现，因此数字零只统计它真正出现在某一位上的那些整数。
        """
        lo, hi = self._check_bounds(lo, hi)
        d = self._check_digit(d)
        if lo > hi:
            return 0
        target = str(d)
        total = 0
        for n in range(lo, hi + 1):
            if target in str(n):
                total += 1
        return total

    def count_monotonic(self, lo, hi):
        """[lo, hi] 里十进制数位从左到右不下降的整数个数。

        单个数位天然满足，数字零同样满足，前导零不计入数位。
        """
        lo, hi = self._check_bounds(lo, hi)
        if lo > hi:
            return 0
        total = 0
        for n in range(lo, hi + 1):
            ds = self._digits(n)
            if all(ds[i] <= ds[i + 1] for i in range(len(ds) - 1)):
                total += 1
        return total

    def count_palindrome(self, lo, hi):
        """[lo, hi] 里十进制表示是回文的整数个数。

        前导零不计入数位，数字零本身按单数位回文处理。
        """
        lo, hi = self._check_bounds(lo, hi)
        if lo > hi:
            return 0
        total = 0
        for n in range(lo, hi + 1):
            s = str(n)
            if s == s[::-1]:
                total += 1
        return total
