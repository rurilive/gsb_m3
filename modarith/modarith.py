"""模运算工具集的基线朴素实现。

本模块只用最直白的循环与枚举完成模运算：求幂靠把底数连乘指数次，
求逆元靠从一到模数减一逐个试乘，解线性同余方程靠枚举全部候选解，
求组合数靠先算阶乘再直接相除后取模。全部朴素但结果正确，规模一大就慢。

异常统一挂在基类 ModarithError 之下。
"""


class ModarithError(Exception):
    """模运算工具集所有异常的基类。"""


class InvalidModulusError(ModarithError):
    """模数不合法（不是整数或不大于一）时抛出。"""


class NegativeExponentError(ModarithError):
    """指数为负时抛出。"""


class InverseNotExistsError(ModarithError):
    """模逆元不存在（模与底数不互素）时抛出。"""


class NoSolutionError(ModarithError):
    """线性同余方程无解时抛出。"""


class NotCoprimeError(ModarithError):
    """需要两两互素却不互素时抛出。"""


class InvalidCombinationError(ModarithError):
    """组合数参数不合法（为负或上标大于下标）时抛出。"""


def _check_modulus(m):
    """校验模数必须是大于一的整数。"""
    if not isinstance(m, int) or isinstance(m, bool):
        raise InvalidModulusError(f"模数必须是整数: {m!r}")
    if m <= 1:
        raise InvalidModulusError(f"模数必须大于一: {m!r}")


def _check_exponent(e):
    """校验指数必须是非负整数。"""
    if not isinstance(e, int) or isinstance(e, bool):
        raise NegativeExponentError(f"指数必须是整数: {e!r}")
    if e < 0:
        raise NegativeExponentError(f"指数不能为负: {e!r}")


def mod_pow(base, exp, mod):
    """朴素模幂：把底数连乘 exp 次，每一步都对 mod 取模。

    用最直白的循环完成，指数一大就慢，但结果正确。
    """
    _check_modulus(mod)
    _check_exponent(exp)
    result = 1 % mod
    for _ in range(exp):
        result = (result * base) % mod
    return result


def mod_inverse(a, m):
    """朴素模逆元：从一到模数减一逐个试乘，看哪一个乘 a 后模 m 等于一。

    找不到（模与底数不互素）时抛 InverseNotExistsError。
    """
    _check_modulus(m)
    target = a % m
    for candidate in range(1, m):
        if (candidate * target) % m == 1:
            return candidate
    raise InverseNotExistsError(f"{a} 在模 {m} 下没有逆元")


def solve_linear_congruence(a, b, m):
    """朴素解线性同余方程 a*x ≡ b (mod m)：枚举零到模数减一的全部候选解。

    无解时抛 NoSolutionError。
    """
    _check_modulus(m)
    for x in range(m):
        if (a * x - b) % m == 0:
            return x
    raise NoSolutionError(f"同余方程 {a}*x ≡ {b} (mod {m}) 无解")


def comb_mod(n, k, mod):
    """朴素组合数取模：先算 n 与 k 的阶乘，再直接相除后取模。

    上标为零时为一，上标大于下标或为负时抛 InvalidCombinationError。
    """
    _check_modulus(mod)
    if n < 0 or k < 0:
        raise InvalidCombinationError(f"组合数参数不能为负: n={n!r} k={k!r}")
    if k > n:
        raise InvalidCombinationError(f"上标不能大于下标: n={n!r} k={k!r}")
    if k == 0:
        return 1 % mod
    numerator = 1
    for i in range(1, n + 1):
        numerator *= i
    denominator = 1
    for i in range(1, k + 1):
        denominator *= i
    for i in range(1, n - k + 1):
        denominator *= i
    return (numerator // denominator) % mod


def crt(residues, moduli):
    """朴素中国剩余定理：逐个模数累乘做区间约束，合并一组两两互素的同余式。

    要求各模数两两互素，否则抛 NotCoprimeError。
    """
    if len(residues) != len(moduli):
        raise ModarithError("余数个数与模数个数不一致")
    if not moduli:
        return 0
    for value in moduli:
        _check_modulus(value)
    for i in range(len(moduli)):
        for j in range(i + 1, len(moduli)):
            if _gcd(moduli[i], moduli[j]) != 1:
                raise NotCoprimeError(f"模数 {moduli[i]} 与 {moduli[j]} 不互素")
    length = 1
    for value in moduli:
        length *= value
    for candidate in range(length):
        if all((candidate - residues[i]) % moduli[i] == 0 for i in range(len(moduli))):
            return candidate
    raise ModarithError("中国剩余定理未找到解")


def _gcd(a, b):
    """朴素辗转相除求最大公约数，供互素判断使用。"""
    a = abs(a)
    b = abs(b)
    while b:
        a, b = b, a % b
    return a
