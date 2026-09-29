"""RetryGuard 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from breakerbox.guard import RetryExhausted, RetryGuard


class TestRetryGuard(unittest.TestCase):
    def test_success_first_try_returns_result(self):
        g = RetryGuard(retries=3)
        self.assertEqual(g.run(lambda: 41 + 1), 42)

    def test_returns_on_second_attempt(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("boom")
            return "ok"

        g = RetryGuard(retries=3)
        self.assertEqual(g.run(flaky), "ok")
        self.assertEqual(len(calls), 2)

    def test_default_is_single_attempt(self):
        calls = []

        def always_fail():
            calls.append(1)
            raise RuntimeError("nope")

        g = RetryGuard()
        with self.assertRaises(RetryExhausted):
            g.run(always_fail)
        self.assertEqual(len(calls), 1)

    def test_attempts_equals_retries_plus_one(self):
        g = RetryGuard(retries=4)

        def always_fail():
            raise RuntimeError("nope")

        with self.assertRaises(RetryExhausted) as ctx:
            g.run(always_fail)
        self.assertEqual(ctx.exception.attempts, 5)

    def test_last_holds_final_exception(self):
        g = RetryGuard(retries=2)

        def always_fail():
            raise KeyError("k")

        with self.assertRaises(RetryExhausted) as ctx:
            g.run(always_fail)
        self.assertIsInstance(ctx.exception.last, KeyError)

    def test_run_passes_args_and_kwargs(self):
        g = RetryGuard(retries=0)
        self.assertEqual(g.run(lambda a, b, c=0: a + b + c, 1, 2, c=3), 6)

    def test_run_or_none_returns_none_on_exhaustion(self):
        g = RetryGuard(retries=1)

        def always_fail():
            raise RuntimeError("nope")

        self.assertIsNone(g.run_or_none(always_fail))

    def test_run_or_none_returns_result_on_success(self):
        g = RetryGuard(retries=1)
        self.assertEqual(g.run_or_none(lambda: "value"), "value")

    def test_retries_property(self):
        self.assertEqual(RetryGuard(retries=7).retries, 7)

    def test_negative_retries_raises(self):
        with self.assertRaises(ValueError):
            RetryGuard(retries=-1)

    def test_clock_is_injectable(self):
        g = RetryGuard(retries=0, clock=lambda: 12.5)
        self.assertEqual(g._clock(), 12.5)


if __name__ == "__main__":
    unittest.main()