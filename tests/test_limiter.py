"""Tests that lock down the baseline CountLimit behaviour.

These tests describe the shipped, naive semantics: a single counter that only
ever grows and recovers only through an explicit reset. They must keep passing
unchanged after the window and token work described in the task is done.
"""

import unittest

from ratelib import CountLimit, RateError


class _FakeClock:
    """A trivially injectable integer clock used by the baseline tests."""

    def __init__(self, now=0):
        self.now = now

    def __call__(self):
        return self.now


class CountLimitTest(unittest.TestCase):
    def test_allows_up_to_limit(self):
        limiter = CountLimit(limit=3, clock=_FakeClock())
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertFalse(limiter.allow())

    def test_used_grows_even_on_reject(self):
        limiter = CountLimit(limit=1, clock=_FakeClock())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertEqual(limiter.used(), 3)

    def test_limit_property(self):
        limiter = CountLimit(limit=5, clock=_FakeClock())
        self.assertEqual(limiter.limit, 5)

    def test_reset_clears_used_and_allows_again(self):
        limiter = CountLimit(limit=2, clock=_FakeClock())
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        limiter.reset()
        self.assertEqual(limiter.used(), 0)
        self.assertTrue(limiter.allow())

    def test_counts_do_not_depend_on_the_clock(self):
        clock = _FakeClock(now=0)
        limiter = CountLimit(limit=2, clock=clock)
        self.assertTrue(limiter.allow())
        clock.now = 10_000
        self.assertTrue(limiter.allow())
        clock.now = 10_000_000
        self.assertFalse(limiter.allow())

    def test_zero_limit_rejects_everything(self):
        limiter = CountLimit(limit=0, clock=_FakeClock())
        self.assertFalse(limiter.allow())

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(RateError):
            CountLimit(limit=-1, clock=_FakeClock())

    def test_non_int_limit_is_rejected(self):
        with self.assertRaises(RateError):
            CountLimit(limit=1.5, clock=_FakeClock())

    def test_missing_clock_is_rejected(self):
        with self.assertRaises(RateError):
            CountLimit(limit=1, clock=None)

    def test_rate_error_is_exception(self):
        self.assertTrue(issubclass(RateError, Exception))


if __name__ == "__main__":
    unittest.main()
