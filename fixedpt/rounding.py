"""定标整数的低位舍入。

乘除落到目标精度时，多出来的低位在这里按舍入模式收口。模式有五种，
名字与含义和 ``decimal`` 模块的口径一致：

- ``trunc``：朝零截断，丢掉低位，正负都往零的方向收（库的默认口径）
- ``half_even``：银行家舍入，到半时往偶数靠
- ``ceil``：向上（朝正无穷）
- ``floor``：向下（朝负无穷）
- ``up``：远离零
"""

from fixedpt.errors import FixedPointError

TRUNC = "trunc"
HALF_EVEN = "half_even"
CEIL = "ceil"
FLOOR = "floor"
UP = "up"

MODES = (TRUNC, HALF_EVEN, CEIL, FLOOR, UP)


def div_trunc(num, den):
    """整数商 num / den，低位朝零截断。

    den 不能为零，其余不设限制。丢掉的那部分不留痕迹。
    """
    if den == 0:
        raise ZeroDivisionError("division by zero: num=%r" % (num,))
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return num // den
    return -((-num) // den)


def div_round(num, den, mode=TRUNC):
    """整数商 num / den 按 mode 舍入成整数。

    den 不能为零。零余数（整除）在任何模式下都是精确商，不会被
    往任何方向抬；非整除时方向由 mode 决定。
    """
    if den == 0:
        raise ZeroDivisionError("division by zero: num=%r" % (num,))
    if den < 0:
        num, den = -num, -den
    if mode == TRUNC:
        return div_trunc(num, den)
    if mode == FLOOR:
        return num // den
    q, r = divmod(num, den)
    if r == 0:
        return q
    if mode == CEIL:
        return q + 1
    if mode == UP:
        return q + 1 if num > 0 else q
    if mode == HALF_EVEN:
        doubled = 2 * r
        if doubled > den or (doubled == den and (q & 1)):
            return q + 1
        return q
    raise FixedPointError("unsupported rounding mode: %r" % (mode,))


def rescale(unscaled, factor, mode=TRUNC):
    """把定标整数 unscaled 降精度，factor 是 10 的幂。

    值由 unscaled / factor 给出，按 mode 舍入到整数。factor 必须为正。
    """
    if factor <= 0:
        raise FixedPointError("factor must be positive: %r" % (factor,))
    if factor == 1:
        return unscaled
    return div_round(unscaled, factor, mode)
