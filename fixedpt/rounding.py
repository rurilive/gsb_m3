"""定标整数的低位裁剪与按模式舍入。

乘除落到目标精度时，多出来的低位在这里裁掉。裁法按模式分：

- truncate: 朝零截断，丢掉低位不看，正负都往零的方向收（默认）。
- away: 远离零，低位非零就往绝对值大的方向进一。
- floor: 向下，朝负无穷收。
- ceil: 向上，朝正无穷收。
- half_even: 银行家舍入，就近取；正好一半时取偶数。

负数与零的方向都跟选定模式一致。实现统一在地板商（divmod）上调整，
不经过浮点，任意大的整数都精确。
"""

from fixedpt.errors import FixedPointError

TRUNCATE = "truncate"
AWAY = "away"
FLOOR = "floor"
CEIL = "ceil"
HALF_EVEN = "half_even"

MODES = (TRUNCATE, AWAY, FLOOR, CEIL, HALF_EVEN)


def check_mode(mode):
    """校验舍入模式名，合法则原样返回。"""
    if mode not in MODES:
        raise FixedPointError("unsupported rounding mode: %r" % (mode,))
    return mode


def div_trunc(num, den):
    """整数商 num / den，低位朝零截断。

    den 不能为零，其余不设限制。丢掉的那部分不留痕迹。
    """
    return div_round(num, den, TRUNCATE)


def div_round(num, den, mode):
    """整数商 num / den，余数按 mode 舍入。

    den 不能为零。divmod 给出地板商与余数，各模式在此基础上调整，
    正负方向由商本身的符号决定，不靠浮点。
    """
    if den == 0:
        raise ZeroDivisionError("division by zero: num=%r" % (num,))
    check_mode(mode)
    q, r = divmod(num, den)
    if r == 0 or mode == FLOOR:
        return q
    if mode == CEIL:
        return q + 1
    negative = (num < 0) != (den < 0)
    if mode == TRUNCATE:
        return q + 1 if negative else q
    if mode == AWAY:
        return q if negative else q + 1
    if mode == HALF_EVEN:
        doubled = 2 * abs(r)
        den_abs = abs(den)
        if doubled > den_abs or (doubled == den_abs and q % 2):
            return q + 1
        return q
