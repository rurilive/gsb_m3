"""ternsearch 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from ternsearch.extremum import (
    DiscreteSequence,
    EnumCounter,
    ExtremumError,
    PeakFinder,
    UnimodalError,
)


def parabola(x):
    return (x - 5) * (x - 5)


def mountain(x):
    return -(x - 3) * (x - 3) + 10


class TestMinimizeMaximize(unittest.TestCase):
    def test_minimize_position_and_value(self):
        f = PeakFinder()
        self.assertEqual(f.minimize(parabola, -10, 10), (5, 0))

    def test_maximize_position_and_value(self):
        f = PeakFinder()
        self.assertEqual(f.maximize(mountain, -10, 10), (3, 10))

    def test_peak_position(self):
        f = PeakFinder()
        self.assertEqual(f.peak_position(mountain, -10, 10), 3)

    def test_minimize_parallel_takes_first(self):
        f = PeakFinder()
        self.assertEqual(f.minimize(lambda x: 7, 0, 9), (0, 7))

    def test_maximize_parallel_takes_first(self):
        f = PeakFinder()
        self.assertEqual(f.maximize(lambda x: -7, 0, 9), (0, -7))

    def test_invalid_range_rejected(self):
        f = PeakFinder()
        with self.assertRaises(ExtremumError):
            f.minimize(parabola, 10, 0)

    def test_non_int_endpoint_rejected(self):
        f = PeakFinder()
        with self.assertRaises(ExtremumError):
            f.minimize(parabola, 0.5, 10)

    def test_bool_endpoint_rejected(self):
        f = PeakFinder()
        with self.assertRaises(ExtremumError):
            f.maximize(parabola, True, 10)

    def test_non_callable_rejected(self):
        f = PeakFinder()
        with self.assertRaises(ExtremumError):
            f.minimize(123, 0, 10)

    def test_eval_count_is_full_scan(self):
        f = PeakFinder()
        self.assertEqual(f.eval_count(parabola, 0, 100), 101)


class TestConvex(unittest.TestCase):
    def test_convex_minimum_interior(self):
        f = PeakFinder()
        self.assertEqual(f.convex_minimum(1, -10, 30, -100, 100), (5, 5))

    def test_convex_minimum_clamped_to_lower(self):
        f = PeakFinder()
        self.assertEqual(f.convex_minimum(1, -10, 30, 8, 100), (8, 14))

    def test_convex_minimum_clamped_to_upper(self):
        f = PeakFinder()
        self.assertEqual(f.convex_minimum(1, -10, 30, -100, 3), (3, 9))

    def test_concave_rejected(self):
        f = PeakFinder()
        with self.assertRaises(UnimodalError):
            f.convex_minimum(-1, -10, 30, -100, 100)

    def test_zero_quadratic_rejected(self):
        f = PeakFinder()
        with self.assertRaises(ExtremumError):
            f.convex_minimum(0, 2, 3, 0, 10)

    def test_integer_maximum_matches_maximize(self):
        f = PeakFinder()
        self.assertEqual(f.integer_maximum(mountain, -10, 10),
                         f.maximize(mountain, -10, 10))


class TestSequence(unittest.TestCase):
    def test_peak_index_basic(self):
        seq = DiscreteSequence([1, 3, 5, 4, 2])
        self.assertEqual(seq.peak_index(), 2)

    def test_peak_index_flat_top_takes_left(self):
        seq = DiscreteSequence([1, 5, 5, 5, 2])
        self.assertEqual(seq.peak_index(), 1)

    def test_first_down_then_up_rejected(self):
        seq = DiscreteSequence([1, 5, 1, 4])
        self.assertFalse(seq.is_unimodal())

    def test_empty_sequence_rejected(self):
        with self.assertRaises(ExtremumError):
            DiscreteSequence([])

    def test_single_point_is_unimodal(self):
        self.assertTrue(DiscreteSequence([9]).is_unimodal())

    def test_non_unimodal_peak_rejected(self):
        seq = DiscreteSequence([1, 5, 1, 4])
        with self.assertRaises(UnimodalError):
            seq.peak_index()

    def test_finder_sequence_peak(self):
        f = PeakFinder()
        self.assertEqual(f.sequence_peak([2, 4, 6, 3, 1]), 2)


class TestCounter(unittest.TestCase):
    def test_wrap_counts_calls(self):
        c = EnumCounter()
        g = c.wrap(parabola)
        g(1)
        g(2)
        self.assertEqual(c.calls, 2)

    def test_reset_zeroes(self):
        c = EnumCounter()
        c.wrap(parabola)(0)
        c.reset()
        self.assertEqual(c.calls, 0)

    def test_wrap_non_callable_rejected(self):
        with self.assertRaises(ExtremumError):
            EnumCounter().wrap(3)


if __name__ == "__main__":
    unittest.main()
