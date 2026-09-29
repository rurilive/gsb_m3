"""FixedWindowLimiter 现有行为的锁定测试。"""

import unittest

from ratelimit.limiter import FixedWindowLimiter


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestFixedWindow(unittest.TestCase):
    def test_allows_within_limit(self):
        c = FakeClock()
        rl = FixedWindowLimiter(3, 10, clock=c)
        self.assertEqual(rl.allow("a"), 1)
        self.assertEqual(rl.allow("a"), 1)
        self.assertEqual(rl.allow("a"), 1)
        self.assertEqual(rl.allow("a"), 0)

    def test_partial_grant(self):
        c = FakeClock()
        rl = FixedWindowLimiter(3, 10, clock=c)
        self.assertEqual(rl.allow("a", 2), 2)
        self.assertEqual(rl.allow("a", 5), 1)  # 只剩 1 个额度

    def test_window_resets(self):
        c = FakeClock()
        rl = FixedWindowLimiter(2, 10, clock=c)
        self.assertEqual(rl.allow("a", 2), 2)
        self.assertEqual(rl.allow("a"), 0)
        c.advance(10)
        self.assertEqual(rl.allow("a"), 1)

    def test_keys_are_independent(self):
        c = FakeClock()
        rl = FixedWindowLimiter(1, 10, clock=c)
        self.assertEqual(rl.allow("a"), 1)
        self.assertEqual(rl.allow("b"), 1)

    def test_remaining(self):
        c = FakeClock()
        rl = FixedWindowLimiter(5, 10, clock=c)
        self.assertEqual(rl.remaining("a"), 5)
        rl.allow("a", 2)
        self.assertEqual(rl.remaining("a"), 3)

    def test_zero_and_negative(self):
        c = FakeClock()
        rl = FixedWindowLimiter(2, 10, clock=c)
        self.assertEqual(rl.allow("a", 0), 0)
        with self.assertRaises(ValueError):
            rl.allow("a", -1)

    def test_invalid_construction(self):
        with self.assertRaises(ValueError):
            FixedWindowLimiter(0, 10)
        with self.assertRaises(ValueError):
            FixedWindowLimiter(1, 0)


if __name__ == "__main__":
    unittest.main()
