"""pctstream: 纯标准库的流式分位数统计小工具。

当前只提供一份朴素实现 NaivePercentileStream，是流式分位数改造前的基线。
纯标准库，无外部依赖。
"""

from pctstream.stream import NaivePercentileStream, StreamError

__all__ = ["NaivePercentileStream", "StreamError"]
