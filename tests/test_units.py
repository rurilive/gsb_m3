"""units 模块的行为基线。"""

import unittest
from decimal import Decimal

from stampkit import units


class GuessUnitTests(unittest.TestCase):
    def test_small_values_are_seconds(self):
        self.assertEqual(units.guess_unit(0), "s")
        self.assertEqual(units.guess_unit(86400), "s")

    def test_millisecond_magnitude(self):
        self.assertEqual(units.guess_unit(1_700_000_000_000), "ms")

    def test_explicit_unit_is_respected(self):
        self.assertEqual(units.to_millis(1500, unit="ms"), 1500)
        self.assertEqual(units.to_seconds(1500, unit="ms"), Decimal("1.5"))


class ToMillisTests(unittest.TestCase):
    def test_seconds_to_millis(self):
        self.assertEqual(units.to_millis(86400, unit="s"), 86_400_000)
        self.assertEqual(units.to_millis(1_700_000_000, unit="s"), 1_700_000_000_000)

    def test_millis_pass_through(self):
        self.assertEqual(units.to_millis(1_700_000_000_123, unit="ms"), 1_700_000_000_123)

    def test_large_second_values_scale_exactly(self):
        self.assertEqual(units.to_millis(315_576_000_000, unit="s"), 315_576_000_000_000)

    def test_guess_on_millisecond_input(self):
        self.assertEqual(units.to_millis(1_700_000_000_123), 1_700_000_000_123)


class ToSecondsTests(unittest.TestCase):
    def test_millis_to_seconds(self):
        self.assertEqual(units.to_seconds(1500, unit="ms"), Decimal("1.5"))
        self.assertEqual(units.to_seconds(86_400_000, unit="ms"), Decimal("86400"))

    def test_seconds_pass_through(self):
        self.assertEqual(units.to_seconds(90, unit="s"), Decimal("90"))


if __name__ == "__main__":
    unittest.main()
