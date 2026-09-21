"""秒级与毫秒级时间戳的单位判定和互相换算。

内部表示统一为整数毫秒。公共接口接受 int 或 float 时间戳，也可以显式
传 unit（"s" 或 "ms"）；不传时按量级启发式判定。
"""

from decimal import Decimal

MS_PER_SECOND = 1000

# 启发式阈值：现代时间戳的秒级取值都在十亿以下，毫秒级远高于十亿，
# 按这个量级切分。
MS_GUESS_THRESHOLD = 10 ** 9


def guess_unit(value):
    """按量级猜测时间戳单位，返回 "s" 或 "ms"。"""
    return "ms" if abs(value) >= MS_GUESS_THRESHOLD else "s"


def to_millis(value, unit=None):
    """把时间戳换算成整数毫秒。

    传入 unit 时按 unit 解释，否则先做启发式判定。秒转毫秒用 Decimal
    换算，避免二进制浮点误差。
    """
    unit = unit or guess_unit(value)
    if unit == "ms":
        return int(value)
    return int(Decimal(value) * MS_PER_SECOND)


def to_seconds(value, unit=None):
    """把时间戳换算成秒。"""
    unit = unit or guess_unit(value)
    if unit == "ms":
        return value / MS_PER_SECOND
    return float(value)
