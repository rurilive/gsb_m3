"""秒级与毫秒级时间戳的单位判定和互相换算。

内部表示统一为整数毫秒。公共接口接受 int 或 float 时间戳，也可以显式
传 unit（"s" 或 "ms"）；不传时按量级启发式判定。
"""

from decimal import ROUND_FLOOR, Decimal

MS_PER_SECOND = 1000

# 启发式阈值：abs(value) >= 10**11 判为毫秒，否则判为秒。
# 十位的秒级时间戳判秒，十三位的毫秒级时间戳判毫秒。
MS_GUESS_THRESHOLD = 10 ** 11


def guess_unit(value):
    """按量级猜测时间戳单位，返回 "s" 或 "ms"。"""
    return "ms" if abs(value) >= MS_GUESS_THRESHOLD else "s"


def _decimal_literal(value):
    """把 float 按其十进制字面值转成 Decimal；int 走精确整数路径。"""
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(repr(float(value)))


def to_millis(value, unit=None):
    """把时间戳换算成整数毫秒。

    传入 unit 时严格按 unit 解释，任何情况下都不再走启发式；否则先做
    量级判定。换算走十进制精确语义，结果向下取整（向负无穷），不引入
    二进制浮点近似。int 入参留在整数路径上，不经过 float/Decimal。
    """
    if unit is None:
        unit = guess_unit(value)
    if unit == "ms":
        if isinstance(value, int):
            return value
        return int(_decimal_literal(value).to_integral_value(rounding=ROUND_FLOOR))
    if isinstance(value, int):
        return value * MS_PER_SECOND
    millis = _decimal_literal(value) * MS_PER_SECOND
    return int(millis.to_integral_value(rounding=ROUND_FLOOR))


def to_seconds(value, unit=None):
    """把时间戳换算成秒。"""
    if unit is None:
        unit = guess_unit(value)
    if unit == "ms":
        if isinstance(value, int):
            return Decimal(value).scaleb(-3)
        return _decimal_literal(value).scaleb(-3)
    return _decimal_literal(value)
