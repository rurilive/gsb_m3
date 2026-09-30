"""combperm: 纯标准库的组合与排列枚举小工具。

当前只提供一份朴素实现 NaiveEnumerator，是组合与排列枚举改造前的基线。
纯标准库，无外部依赖。
"""

from combperm.enumerate import CombPermError, NaiveEnumerator

__all__ = ["NaiveEnumerator", "CombPermError"]
