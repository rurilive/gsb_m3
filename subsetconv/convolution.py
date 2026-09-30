"""集合函数的朴素卷积实现。

下标是集合的比特掩码，长度必须是正整数二次方。四种卷积都用最直白的
逐对累加写法：枚举一个下标，再枚举另一个下标，按对应集合运算把乘积
累加进结果下标。结果正确，但下标对是二次方，整体到四次方量级。
"""


class ConvolutionError(Exception):
    """卷积工具包统一异常基类。"""


class InvalidLengthError(ConvolutionError):
    """长度不是正整数二次方。"""


class LengthMismatchError(ConvolutionError):
    """两个数组长度不一致。"""


def is_power_of_two(n):
    """正整数二次方返回 True，其余（含零与负数）返回 False。"""
    return n > 0 and (n & (n - 1)) == 0


class SetFunction(object):
    """把一个数组当作集合函数，下标即集合的比特掩码。"""

    def __init__(self, values):
        vals = [v for v in values]
        n = len(vals)
        if not is_power_of_two(n):
            raise InvalidLengthError(
                "length must be a positive power of two, got %d" % n
            )
        self._vals = vals
        self._n = n

    @property
    def size(self):
        return self._n

    def as_list(self):
        return list(self._vals)

    def __len__(self):
        return self._n

    def __getitem__(self, index):
        return self._vals[index]

    def __eq__(self, other):
        return isinstance(other, SetFunction) and self._vals == other._vals

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "SetFunction(%r)" % (self._vals,)

    def pair_count(self):
        """朴素逐对累加的下标对数量。"""
        return self._n * self._n

    def _check_partner(self, other):
        if not isinstance(other, SetFunction):
            raise ConvolutionError("partner must be a SetFunction")
        if other._n != self._n:
            raise LengthMismatchError(
                "size mismatch: %d vs %d" % (self._n, other._n)
            )

    def or_convolve(self, other):
        """或卷积：结果下标等于两个下标按位或。"""
        self._check_partner(other)
        n = self._n
        a = self._vals
        b = other._vals
        res = [0] * n
        for i in range(n):
            ai = a[i]
            for j in range(n):
                res[i | j] += ai * b[j]
        return SetFunction(res)

    def and_convolve(self, other):
        """与卷积：结果下标等于两个下标按位与。"""
        self._check_partner(other)
        n = self._n
        a = self._vals
        b = other._vals
        res = [0] * n
        for i in range(n):
            ai = a[i]
            for j in range(n):
                res[i & j] += ai * b[j]
        return SetFunction(res)

    def xor_convolve(self, other):
        """异或卷积：结果下标等于两个下标按位异或。"""
        self._check_partner(other)
        n = self._n
        a = self._vals
        b = other._vals
        res = [0] * n
        for i in range(n):
            ai = a[i]
            for j in range(n):
                res[i ^ j] += ai * b[j]
        return SetFunction(res)

    def subset_convolve(self, other):
        """不交并子集卷积：只累计两个下标不相交的情形。"""
        self._check_partner(other)
        n = self._n
        a = self._vals
        b = other._vals
        res = [0] * n
        for i in range(n):
            ai = a[i]
            for j in range(n):
                if (i & j) == 0:
                    res[i | j] += ai * b[j]
        return SetFunction(res)
