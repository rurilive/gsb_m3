"""Baseline rate limiting primitives.

This module intentionally contains only the most naive limiter we could ship:
:class:`CountLimit`. It keeps a counter of calls and rejects everything after
the configured budget has been used up. There is no window, no time based
recovery, no per-key buckets and no rolling clock support. The class accepts a
clock object at construction time but never reads it; the injected clock only
starts to matter once the window and token work described in the task is done.
"""


class RateError(Exception):
    """Base class for every error raised by ratelib."""


class CountLimit:
    """A plain fixed-count limiter.

    The limiter allows at most ``limit`` calls over its whole lifetime. Once
    that many calls have been allowed, every further call to :meth:`allow` is
    rejected. No time is consulted; the used counter only ever grows and can
    only be brought back to zero by an explicit call to :meth:`reset`.
    """

    def __init__(self, limit, clock):
        """Create a limiter capped at ``limit`` calls.

        ``clock`` is an injected, callable integer clock supplied by the
        caller. The baseline implementation stores it untouched and never
        calls it; keeping the parameter here means the future window work can
        read time without changing the constructor signature.
        """
        if not isinstance(limit, int):
            raise RateError("limit must be an int")
        if limit < 0:
            raise RateError("limit must be non-negative")
        if clock is None:
            raise RateError("clock is required")
        self._limit = limit
        self._clock = clock
        self._used = 0

    @property
    def limit(self):
        return self._limit

    @property
    def clock(self):
        return self._clock

    def allow(self):
        """Record one call and return whether it is allowed.

        Returns ``True`` while fewer than ``limit`` calls have been recorded,
        otherwise ``False``. The internal used counter is incremented for every
        call regardless of the outcome, mirroring a plain tally.
        """
        self._used += 1
        return self._used <= self._limit

    def used(self):
        """Return how many calls have been recorded so far."""
        return self._used

    def reset(self):
        """Set the used counter back to zero.

        The baseline has no automatic recovery, so this has to be called by
        hand once the budget has run out.
        """
        self._used = 0
