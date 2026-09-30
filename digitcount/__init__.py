"""digitcount：改造前基线的朴素区间数位计数工具。

提供 NaiveDigitCounter 类，围绕闭区间 [lo, hi] 里全部非负整数，按数位条件做
四类计数：各位数字之和对某模取余等于某值、十进制表示里含某个数字、相邻数位
满足单调关系、十进制表示是回文。当前实现一律把区间里每个整数翻成十进制串，
逐位分解后再逐条判定，区间一大就线性退化，且没有任何跨整数复用的状态结构。
"""

from .counter import (
    DigitCountError,
    InvalidBoundError,
    InvalidDigitError,
    InvalidModError,
    NaiveDigitCounter,
)

__all__ = [
    "NaiveDigitCounter",
    "DigitCountError",
    "InvalidBoundError",
    "InvalidDigitError",
    "InvalidModError",
]
