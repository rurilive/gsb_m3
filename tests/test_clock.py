"""SimClock 的行为基线。"""

import unittest

from membersim.clock import SimClock


class TestSimClock(unittest.TestCase):
    def test_starts_at_zero_by_default(self):
        self.assertEqual(SimClock().now, 0.0)

    def test_custom_start(self):
        self.assertEqual(SimClock(2.5).now, 2.5)

    def test_advance_returns_new_now(self):
        clock = SimClock()
        self.assertEqual(clock.advance(0.5), 0.5)
        self.assertEqual(clock.advance(1.5), 2.0)
        self.assertEqual(clock.now, 2.0)

    def test_advance_must_be_positive(self):
        clock = SimClock()
        with self.assertRaises(ValueError):
            clock.advance(0)
        with self.assertRaises(ValueError):
            clock.advance(-1)

    def test_negative_start_rejected(self):
        with self.assertRaises(ValueError):
            SimClock(-0.1)


if __name__ == "__main__":
    unittest.main()
