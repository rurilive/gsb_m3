"""ratelimit: 固定时间窗限流器。

当前只提供一份朴素实现 TimestampLimiter，按固定时间窗口统计请求量，
每笔判定线性扫描全部时间戳，是滑动窗口改造前的基线。
纯标准库，无外部依赖。
"""

from ratelimit.core import DEFAULT_LABEL, RateLimitError, TimestampLimiter, naive_scan

__all__ = ["DEFAULT_LABEL", "RateLimitError", "TimestampLimiter", "naive_scan"]
