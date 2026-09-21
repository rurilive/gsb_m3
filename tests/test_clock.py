import time
import unittest

from tokengate import Clock, ManualClock


class ClockTests(unittest.TestCase):
    def test_wall_clock_tracks_time(self):
        before = time.time()
        now = Clock().now()
        self.assertIsInstance(now, float)
        self.assertGreaterEqual(now, before - 1)

    def test_manual_clock_starts_where_told(self):
        self.assertEqual(ManualClock(500.0).now(), 500.0)
        self.assertEqual(ManualClock().now(), 1_700_000_000.0)

    def test_advance_moves_forward(self):
        clock = ManualClock(100.0)
        self.assertEqual(clock.advance(0.5), 100.5)
        self.assertEqual(clock.advance(59.5), 160.0)

    def test_set_jumps(self):
        clock = ManualClock(100.0)
        self.assertEqual(clock.set(42), 42.0)
        self.assertEqual(clock.now(), 42.0)

    def test_backwards_is_refused(self):
        clock = ManualClock(100.0)
        with self.assertRaises(ValueError):
            clock.advance(-1)
        self.assertEqual(clock.now(), 100.0)


if __name__ == "__main__":
    unittest.main()
