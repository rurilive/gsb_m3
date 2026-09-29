"""breakerbox: 可失败调用的朴素重试包装（改造前基线）。"""

from .guard import RetryExhausted, RetryGuard

__all__ = ["RetryGuard", "RetryExhausted"]