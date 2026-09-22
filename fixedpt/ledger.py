"""清算例行：累加、计息、分账与对账。

金额按域精度存放，10.00 在 scale=6 下是 Fixed(10000000, 6)。
分账是硬约束：各份之和与总额一分不差，尾数按最小单位摊给头几份。
"""

from fixedpt.errors import FixedPointError
from fixedpt.number import Fixed


def total_of(domain, values):
    """逐笔累加，每步都过域收口。"""
    acc = domain.fixed(0)
    for value in values:
        acc = domain.add(acc, value)
    return acc


def apply_rate(domain, amount, rate, out_scale=None):
    """按 rate 给一笔钱计息，乘积落到账目精度。"""
    return domain.mul(amount, rate, out_scale)


def split(domain, amount, parts):
    """把 amount 摊到 parts 份上。

    先整摊，余下的最小单位（10 的负 scale 次方）逐份加给头几份，
    各份之和与 amount 一分不差。parts 必须为正整数。
    """
    if isinstance(parts, bool) or not isinstance(parts, int) or parts <= 0:
        raise FixedPointError("parts must be a positive int: %r" % (parts,))
    base = domain.div(amount, Fixed(parts, 0))
    remainder = amount.unscaled - base.unscaled * parts
    step = 1 if remainder >= 0 else -1
    out = []
    for index in range(parts):
        extra = step if abs(remainder) > index else 0
        out.append(Fixed(base.unscaled + extra, amount.scale))
    return out


def reconcile(domain, amounts, expected):
    """对账：合计与 expected 的差，零表示平。"""
    return domain.sub(total_of(domain, amounts), expected)
