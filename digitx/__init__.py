"""digitx：朴素数位计数工具（改造前基线）。

提供 BruteDigits 类，围绕从一到某个上界 n 的整数做四类计数：
数位含某数字的整数个数、全部整数各位数字之和、数值不大于给定上界的
整数个数、能被 m 整除的整数个数。当前实现一律从一到上界逐个整数枚举，
逐位检查，上界一大就线性退化。
"""

from .count import BruteDigits, DigitError, InvalidBoundError, InvalidDigitError

__all__ = [
    "BruteDigits",
    "DigitError",
    "InvalidBoundError",
    "InvalidDigitError",
]
