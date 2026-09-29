"""statlib: 纯标准库的流式统计小工具。

当前只提供一份朴素实现 NaiveStats，是流式中位数改造前的基线。
纯标准库，无外部依赖。
"""

from statlib.running import NaiveStats

__all__ = ["NaiveStats"]
