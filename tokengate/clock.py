"""Time sources.

Anything in the package that needs the current time takes a clock, so that
callers and tests can pin time instead of sleeping.
"""

import time


class Clock:
    """Thin wrapper around the system wall clock."""

    def now(self):
        """Return the current time as seconds since the epoch (float)."""
        return time.time()


class ManualClock:
    """Deterministic clock driven by hand, for tests and demos."""

    def __init__(self, start=1_700_000_000.0):
        self._now = float(start)

    def now(self):
        return self._now

    def advance(self, seconds):
        """Move forward by ``seconds`` and return the new time."""
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("manual clock cannot move backwards")
        self._now += seconds
        return self._now

    def set(self, when):
        """Jump to an absolute time and return it."""
        self._now = float(when)
        return self._now
