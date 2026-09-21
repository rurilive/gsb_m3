"""时间源读法的锁定测试。"""

import unittest

from steadyclock.source import ManualSource, SystemSource, TimeSource


class TestManualSource(unittest.TestCase):
    def test_readings_start_aligned_unless_told_otherwise(self):
        source = ManualSource(wall=1000.0)
        self.assertAlmostEqual(source.wall(), 1000.0)
        self.assertAlmostEqual(source.monotonic(), 1000.0)
        offset_source = ManualSource(wall=100.0, monotonic=10.0)
        self.assertAlmostEqual(offset_source.wall(), 100.0)
        self.assertAlmostEqual(offset_source.monotonic(), 10.0)

    def test_sleep_advances_both_readings(self):
        source = ManualSource(wall=100.0, monotonic=10.0)
        source.sleep(2.5)
        self.assertAlmostEqual(source.wall(), 102.5)
        self.assertAlmostEqual(source.monotonic(), 12.5)

    def test_step_wall_moves_only_the_wall_reading(self):
        source = ManualSource(wall=100.0, monotonic=10.0)
        source.step_wall(-40.0)
        self.assertAlmostEqual(source.wall(), 60.0)
        self.assertAlmostEqual(source.monotonic(), 10.0)
        source.step_wall(7.0)
        self.assertAlmostEqual(source.wall(), 67.0)
        self.assertAlmostEqual(source.monotonic(), 10.0)

    def test_set_wall_moves_only_the_wall_reading(self):
        source = ManualSource(wall=100.0, monotonic=10.0)
        source.set_wall(2_000_000.0)
        self.assertAlmostEqual(source.wall(), 2_000_000.0)
        self.assertAlmostEqual(source.monotonic(), 10.0)

    def test_negative_sleep_is_rejected(self):
        with self.assertRaises(ValueError):
            ManualSource().sleep(-0.001)


class TestSystemSource(unittest.TestCase):
    def test_readings_are_floats_and_monotonic_never_goes_back(self):
        source = SystemSource()
        start = source.monotonic()
        self.assertIsInstance(start, float)
        self.assertIsInstance(source.wall(), float)
        self.assertGreaterEqual(source.monotonic(), start)

    def test_sleep_advances_monotonic(self):
        source = SystemSource()
        start = source.monotonic()
        source.sleep(0.01)
        self.assertGreaterEqual(source.monotonic() - start, 0.005)


class TestContract(unittest.TestCase):
    def test_base_class_has_no_clock_behind_it(self):
        source = TimeSource()
        with self.assertRaises(NotImplementedError):
            source.wall()
        with self.assertRaises(NotImplementedError):
            source.monotonic()
        with self.assertRaises(NotImplementedError):
            source.sleep(1.0)


if __name__ == "__main__":
    unittest.main()
