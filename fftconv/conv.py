"""fftconv: 多项式乘法的朴素实现。

当前只有一份朴素实现：两个多项式相乘用双重循环逐对系数相乘再按幂次累加，
复杂度是两个多项式长度的乘积，规模一大就上到平方量级。配套还提供横坐标
求值、由根逐个相乘构造、求值点与点值表的配对校验、模数是否合法、长度是否
为二的幂、以及变换长度能否整除模数减一这些朴素辅助。结果正确，慢在规模。

改用迭代版快速傅里叶变换做点值相乘再逆变换，或用模素数下的数论变换交叉
核对，以及边界覆盖与确定性要求，见任务描述。
"""


class Erro(Exception):
    """fftconv 全部异常的基类。"""


class IllegalArgument(Erro):
    """系数序列或参数本身不合法。"""


class IllegalLength(Erro):
    """长度不是二的幂，或两条序列长度对不上。"""


class IllegalModulus(Erro):
    """模数不是素数，或长度不能整除模数减一。"""


class PointMismatch(Erro):
    """求值点与点值表的长度对不上。"""


def check_coeffs(coeffs):
    """校验系数序列，返回逐项取整后的普通列表。"""
    if isinstance(coeffs, (str, bytes)) or not hasattr(coeffs, "__iter__"):
        raise IllegalArgument("coefficients must be an iterable")
    out = []
    for c in coeffs:
        if isinstance(c, bool) or not isinstance(c, int):
            raise IllegalArgument("coefficient must be an int")
        out.append(c)
    return out


def trim(coeffs):
    """去掉最高次的零项，零多项式用空列表表示。"""
    out = check_coeffs(coeffs)
    while out and out[-1] == 0:
        out.pop()
    return out


def is_power_of_two(n):
    """判断是否为正的二的幂。"""
    return (
        isinstance(n, int)
        and not isinstance(n, bool)
        and n > 0
        and (n & (n - 1)) == 0
    )


def is_prime(m):
    """试除法判定素数，朴素但正确。"""
    if isinstance(m, bool) or not isinstance(m, int) or m < 2:
        return False
    if m < 4:
        return True
    if m % 2 == 0:
        return False
    d = 3
    while d * d <= m:
        if m % d == 0:
            return False
        d += 2
    return True


def check_modulus(m):
    """校验模数，必须是至少为二的整数且为素数。"""
    if isinstance(m, bool) or not isinstance(m, int) or m < 2:
        raise IllegalModulus("modulus must be an int at least two")
    if not is_prime(m):
        raise IllegalModulus("modulus must be prime")
    return m


def check_transform_length(n, m):
    """校验变换长度，必须是二的幂且整除模数减一。"""
    m = check_modulus(m)
    if not is_power_of_two(n):
        raise IllegalLength("transform length must be a power of two")
    if (m - 1) % n != 0:
        raise IllegalLength("transform length must divide modulus minus one")
    return n


def result_length(na, nb):
    """按两条序列的长度推算卷积结果的长度。"""
    for n in (na, nb):
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise IllegalArgument("length must be a non-negative int")
    if na == 0 or nb == 0:
        return 0
    return na + nb - 1


def check_pointwise(xs, ys):
    """校验求值点与点值表长度一致，返回两个普通列表。"""
    xs = list(xs)
    ys = list(ys)
    if len(xs) != len(ys):
        raise PointMismatch("evaluation points and values must have equal length")
    return xs, ys


class Poly:
    """低位在前的系数表表示的多项式，构造时去掉高次零项。"""

    def __init__(self, coeffs):
        self.coeffs = trim(coeffs)

    def degree(self):
        """次数，零多项式记为负一。"""
        return len(self.coeffs) - 1

    def is_zero(self):
        """是否为零多项式。"""
        return not self.coeffs

    def to_list(self):
        """返回系数表的副本。"""
        return list(self.coeffs)

    def __eq__(self, other):
        return isinstance(other, Poly) and self.coeffs == other.coeffs

    def __repr__(self):
        return "Poly(%r)" % (self.coeffs,)

    def add(self, other):
        """逐项对齐相加。"""
        a, b = self.coeffs, other.coeffs
        n = max(len(a), len(b))
        out = [0] * n
        for i in range(n):
            x = a[i] if i < len(a) else 0
            y = b[i] if i < len(b) else 0
            out[i] = x + y
        return Poly(out)

    def sub(self, other):
        """逐项对齐相减。"""
        a, b = self.coeffs, other.coeffs
        n = max(len(a), len(b))
        out = [0] * n
        for i in range(n):
            x = a[i] if i < len(a) else 0
            y = b[i] if i < len(b) else 0
            out[i] = x - y
        return Poly(out)

    def mul_naive(self, other):
        """双重循环逐对系数相乘，再按幂次累加，平方级复杂度。"""
        a, b = self.coeffs, other.coeffs
        if not a or not b:
            return Poly([])
        out = [0] * (len(a) + len(b) - 1)
        for i, x in enumerate(a):
            if x == 0:
                continue
            for j, y in enumerate(b):
                out[i + j] += x * y
        return Poly(out)

    def evaluate(self, x):
        """霍纳方式在横坐标 x 处求值。"""
        acc = 0
        for c in reversed(self.coeffs):
            acc = acc * x + c
        return acc

    def reduce_mod(self, modulus):
        """逐项对模数归一，负数落到非负区间。"""
        m = check_modulus(modulus)
        return Poly([c % m for c in self.coeffs])


def convolve_naive(a, b):
    """两条系数序列的朴素卷积，返回普通列表。"""
    return Poly(a).mul_naive(Poly(b)).to_list()


def evaluate_many(coeffs, xs):
    """在一串横坐标上逐个求值，返回与输入等长的列表。"""
    p = Poly(coeffs)
    return [p.evaluate(x) for x in xs]


def from_roots(roots):
    """由根逐个相乘构造多项式。"""
    p = Poly([1])
    for r in check_coeffs(roots):
        p = p.mul_naive(Poly([-r, 1]))
    return p
