"""秒级与毫秒级时间戳的单位判定和互相换算。

内部表示统一为整数毫秒。公共接口接受 int 或 float 时间戳，也可以显式
传 unit（"s" 或 "ms"）；不传时按量级启发式判定。
"""

from decimal import ROUND_FLOOR, Decimal

MS_PER_SECOND = 1000

# 启发式阈值：abs(value) >= 10**11 判为毫秒（十三位毫秒时间戳），
# 否则判为秒（十位秒级时间戳）。
MS_GUESS_THRESHOLD = 10 ** 11


def guess_unit(value):
    """按量级猜测时间戳单位，返回 "s" 或 "ms"。"""
    return "ms" if abs(value) >= MS_GUESS_THRESHOLD else "s"


def _as_decimal(value):
    """按十进制字面值解析入参。

    float 经过 str() 转成 Decimal，得到的是 JSON 字面量
    （如 1234567890.5）对应的十进制值，不引入二进制浮点近似；
    int 精确转换，Decimal 原样保留。
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def to_millis(value, unit=None):
    """把时间戳换算成整数毫秒。

    传入 unit 时只按 unit 解释，绝不走启发式；否则先按量级判定。
    整数输入全程走整数运算；浮点输入按十进制字面值经 Decimal 精确换算，
    结果向下取整（向负无穷）。
    """
    if unit is None:
        unit = guess_unit(value)
    if unit == "ms":
        if isinstance(value, int):
            return value
        return int(_as_decimal(value).to_integral_value(rounding=ROUND_FLOOR))
    if isinstance(value, int):
        return value * MS_PER_SECOND
    millis = _as_decimal(value) * MS_PER_SECOND
    return int(millis.to_integral_value(rounding=ROUND_FLOOR))


def to_seconds(value, unit=None):
    """把时间戳换算成秒，返回十进制精确值（Decimal）。"""
    if unit is None:
        unit = guess_unit(value)
    if unit == "ms":
        return _as_decimal(value) / MS_PER_SECOND
    return _as_decimal(value)
