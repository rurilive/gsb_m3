"""coinchange: 纯标准库的零钱兑换小工具。

当前只提供一份朴素实现 NaiveCoinChange，是零钱兑换动态规划改造前的基线。
纯标准库，无外部依赖。
"""

from coinchange.core import NaiveCoinChange, CoinChangeError

__all__ = ["NaiveCoinChange", "CoinChangeError"]
