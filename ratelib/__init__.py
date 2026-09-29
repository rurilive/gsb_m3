"""ratelib: a small, dependency-free rate limiting toolkit.

The current release ships a single primitive, :class:`CountLimit`, which only
counts how many times it has been asked for permission and rejects everything
after a fixed budget has been used up. Time is not consulted anywhere in this
version, so there is no window and no automatic recovery.
"""

from .limiter import CountLimit, RateError

__all__ = ["CountLimit", "RateError"]
