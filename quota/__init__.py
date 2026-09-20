"""quota: 网关限流模块。"""
from .limiter import DEFAULT_KEY, FixedWindowLimiter

__all__ = ["FixedWindowLimiter", "DEFAULT_KEY"]
