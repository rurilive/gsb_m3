"""超时与耗时口径的锁定测试，时间源注入。"""

import unittest

from steadyclock.deadline import Deadline, Stopwatch
from steadyclock.source import ManualSource


class TestDeadline(unittest.TestCase):
    def setUp(self):
        self.source = ManualSource(wall=1000.0)

    def test_remaining_shrinks_as_time_moves(self):
        deadline = Deadline(self.source, 5.0)
        self.assertAlmostEqual(deadline.remaining(), 5.0)
        self.source.sleep(2.0)
        self.assertAlmostEqual(deadline.elapsed(), 2.0)
        self.assertAlmostEqual(deadline.remaining(), 3.0)
        self.assertFalse(deadline.expired())

    def test_expiry_boundary(self):
        deadline = Deadline(self.source, 1.0)
        self.source.sleep(0.5)
        self.assertAlmostEqual(deadline.remaining(), 0.5)
        self.assertFalse(deadline.expired())
        self.source.sleep(0.5)
        self.assertAlmostEqual(deadline.remaining(), 0.0)
        self.assertTrue(deadline.expired())

    def test_timeout_is_readable_and_not_negative(self):
        deadline = Deadline(self.source, 2.5)
        self.assertAlmostEqual(deadline.timeout, 2.5)
        with self.assertRaises(ValueError):
            Deadline(self.source, -0.5)

    def test_extend_pushes_expiry_back(self):
        deadline = Deadline(self.source, 1.0)
        self.source.sleep(1.5)
        self.assertTrue(deadline.expired())
        deadline.extend(2.0)
        self.assertAlmostEqual(deadline.timeout, 3.0)
        self.assertAlmostEqual(deadline.remaining(), 1.5)
        self.assertFalse(deadline.expired())

    def test_reset_starts_over(self):
        deadline = Deadline(self.source, 4.0)
        self.source.sleep(3.0)
        deadline.reset()
        self.assertAlmostEqual(deadline.elapsed(), 0.0)
        self.assertAlmostEqual(deadline.remaining(), 4.0)


class TestStopwatch(unittest.TestCase):
    def setUp(self):
        self.source = ManualSource(wall=1000.0)

    def test_elapsed_measures_forward_motion(self):
        watch = Stopwatch(self.source)
        self.source.sleep(0.25)
        self.assertAlmostEqual(watch.elapsed(), 0.25)

    def test_restart_starts_over(self):
        watch = Stopwatch(self.source)
        self.source.sleep(0.25)
        watch.restart()
        self.source.sleep(0.1)
        self.assertAlmostEqual(watch.elapsed(), 0.1)


if __name__ == "__main__":
    unittest.main()
