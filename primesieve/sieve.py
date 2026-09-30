"""primesieve 的朴素素数筛与整数分解实现（改造前的现状）。

现在只有一条路径：求不超过某上界的全部素数，是对每个数从二试到它的
平方根、逐个试除判素；分解一个整数是从二开始反复试除它的因子；求不超
过上界的素数个数与欧拉函数值也走同一套试除。没有线性筛，没有最小质因
子表，一次分解要按被分解数的大小反复试除。线性时间筛出素数、顺带记录
每个数的最小质因子并据此快速分解见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class ValueTypeError(Erro):
    """参数类型不合法的输入。"""


class NumberRangeError(Erro):
    """整数的取值范围不合法。"""


def _require_int(value, name):
    """要求 value 是整数（布尔值不算），否则抛 ValueTypeError。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueTypeError("%s must be an int" % (name,))
    return value


class Sieve:
    """给定上界，用逐数试除这一种方式做判素、分解与相关统计。"""

    def __init__(self, upper):
        _require_int(upper, "upper")
        if upper < 0:
            raise NumberRangeError("upper must not be negative")
        self._upper = upper
        self._divisions = 0

    def upper(self):
        """返回构造时给定的上界。"""
        return self._upper

    def reset_counts(self):
        """把试除计数清零。"""
        self._divisions = 0

    def trial_divisions(self):
        """自上次清零以来累计试除了多少次。"""
        return self._divisions

    def _is_prime_naive(self, x):
        """朴素判素：从二试到平方根，逐个试除，累计试除次数。"""
        if x < 2:
            return False
        if x == 2:
            return True
        if x % 2 == 0:
            return False
        d = 3
        while d * d <= x:
            self._divisions += 1
            if x % d == 0:
                return False
            d += 2
        return True

    def is_prime(self, x):
        """判断单个整数是否素数，负数、零与一都返回假。"""
        _require_int(x, "x")
        return self._is_prime_naive(x)

    def primes(self):
        """返回不超过上界的全部素数，升序元组（逐个试除判定）。"""
        result = []
        for x in range(2, self._upper + 1):
            if self._is_prime_naive(x):
                result.append(x)
        return tuple(result)

    def _factorize_naive(self, x):
        """朴素分解：从二起反复试除因子，返回升序质因子元组（含重数）。"""
        result = []
        n = x
        if n < 2:
            return tuple(result)
        d = 2
        while d * d <= n:
            while True:
                self._divisions += 1
                if n % d != 0:
                    break
                result.append(d)
                n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            result.append(n)
        return tuple(result)

    def factorize(self, x):
        """分解单个整数，返回升序质因子元组；一返回空，零与负数报错。"""
        _require_int(x, "x")
        if x < 1:
            raise NumberRangeError("x must be positive")
        return self._factorize_naive(x)

    def factorize_all(self, values):
        """分解一批整数，按输入顺序返回各自的质因子元组。"""
        if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
            raise ValueTypeError("values must be a sequence of int")
        result = []
        for x in values:
            result.append(self.factorize(x))
        return tuple(result)

    def euler_phi(self, x):
        """返回不超过 x 且与 x 互素的整数个数；一返回一，零与负数报错。"""
        _require_int(x, "x")
        if x < 1:
            raise NumberRangeError("x must be positive")
        if x == 1:
            return 1
        value = x
        last = None
        for p in self._factorize_naive(x):
            if p == last:
                continue
            last = p
            value = value // p * (p - 1)
        return value

    def count_primes(self, lo, hi):
        """统计闭区间 [lo, hi] 内的素数个数（逐个试除判定）。"""
        _require_int(lo, "lo")
        _require_int(hi, "hi")
        if lo < 0 or hi < lo:
            raise NumberRangeError("require 0 <= lo <= hi")
        total = 0
        for x in range(lo, hi + 1):
            if self._is_prime_naive(x):
                total += 1
        return total
