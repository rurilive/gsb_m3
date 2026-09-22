"""舍入模式与溢出策略：div_round 方向、Domain 模式配置、越界收口。"""

import unittest

from fixedpt import Domain, DomainOverflow, Fixed, FixedPointError
from fixedpt.rounding import MODES, div_round, div_trunc


class TestDivRound(unittest.TestCase):

    def test_trunc_toward_zero(self):
        self.assertEqual(div_round(7, 2, "truncate"), 3)
        self.assertEqual(div_round(-7, 2, "truncate"), -3)
        self.assertEqual(div_round(7, -2, "truncate"), -3)
        self.assertEqual(div_round(-7, -2, "truncate"), 3)
        self.assertEqual(div_round(0, 5, "truncate"), 0)

    def test_away_from_zero(self):
        self.assertEqual(div_round(7, 2, "away"), 4)
        self.assertEqual(div_round(-7, 2, "away"), -4)
        self.assertEqual(div_round(7, -2, "away"), -4)
        self.assertEqual(div_round(-7, -2, "away"), 4)
        self.assertEqual(div_round(6, 2, "away"), 3)

    def test_floor_toward_negative_infinity(self):
        self.assertEqual(div_round(7, 2, "floor"), 3)
        self.assertEqual(div_round(-7, 2, "floor"), -4)
        self.assertEqual(div_round(7, -2, "floor"), -4)
        self.assertEqual(div_round(-7, -2, "floor"), 3)

    def test_ceil_toward_positive_infinity(self):
        self.assertEqual(div_round(7, 2, "ceil"), 4)
        self.assertEqual(div_round(-7, 2, "ceil"), -3)
        self.assertEqual(div_round(7, -2, "ceil"), -3)
        self.assertEqual(div_round(-7, -2, "ceil"), 4)

    def test_half_even_ties_to_even(self):
        self.assertEqual(div_round(5, 2, "half_even"), 2)    # 2.5 -> 2
        self.assertEqual(div_round(15, 10, "half_even"), 2)  # 1.5 -> 2
        self.assertEqual(div_round(25, 10, "half_even"), 2)  # 2.5 -> 2
        self.assertEqual(div_round(35, 10, "half_even"), 4)  # 3.5 -> 4
        self.assertEqual(div_round(-5, 2, "half_even"), -2)   # -2.5 -> -2
        self.assertEqual(div_round(-15, 10, "half_even"), -2)
        self.assertEqual(div_round(-25, 10, "half_even"), -2)
        self.assertEqual(div_round(-35, 10, "half_even"), -4)

    def test_half_even_non_ties_round_nearest(self):
        self.assertEqual(div_round(13, 10, "half_even"), 1)   # 1.3 -> 1
        self.assertEqual(div_round(17, 10, "half_even"), 2)   # 1.7 -> 2
        self.assertEqual(div_round(-13, 10, "half_even"), -1)
        self.assertEqual(div_round(-17, 10, "half_even"), -2)

    def test_exact_division_all_modes_agree(self):
        for mode in MODES:
            self.assertEqual(div_round(6, 3, mode), 2)
            self.assertEqual(div_round(-6, 3, mode), -2)
            self.assertEqual(div_round(0, 7, mode), 0)

    def test_div_trunc_matches_truncate_mode(self):
        for num in (-9, -7, -1, 0, 1, 7, 9):
            for den in (-4, -2, 2, 4):
                self.assertEqual(div_trunc(num, den), div_round(num, den, "truncate"))

    def test_zero_denominator(self):
        for mode in MODES:
            with self.assertRaises(ZeroDivisionError):
                div_round(1, 0, mode)
        with self.assertRaises(ZeroDivisionError):
            div_trunc(1, 0)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(FixedPointError):
            div_round(1, 1, "bogus")


class TestDomainRoundingConfig(unittest.TestCase):

    def test_default_is_truncate(self):
        self.assertEqual(Domain().rounding, "truncate")

    def test_accepts_all_modes(self):
        for mode in MODES:
            self.assertEqual(Domain(rounding=mode).rounding, mode)

    def test_rejects_bad_mode(self):
        with self.assertRaises(FixedPointError):
            Domain(rounding="bogus")
        with self.assertRaises(FixedPointError):
            Domain(rounding=None)


class TestDomainMulDivRounding(unittest.TestCase):

    def test_domain_default_mode_applies(self):
        d = Domain(bits=64, scale=2, rounding="ceil")
        # 0.07 / 0.02 = 3.5，向上进 3.5 -> 4 at scale 0
        self.assertEqual(d.div(Fixed(7, 2), Fixed(2, 2), out_scale=0), Fixed(4, 0))
        self.assertEqual(d.div(Fixed(-7, 2), Fixed(2, 2), out_scale=0), Fixed(-3, 0))

    def test_per_call_override(self):
        d = Domain(bits=64, scale=2, rounding="ceil")
        a, b = Fixed(7, 2), Fixed(2, 2)
        self.assertEqual(d.div(a, b, out_scale=0, rounding="floor"), Fixed(3, 0))
        self.assertEqual(d.div(a, b, out_scale=0), Fixed(4, 0))
        with self.assertRaises(FixedPointError):
            d.div(a, b, out_scale=0, rounding="bogus")

    def test_mul_rounds_half_even(self):
        d = Domain(bits=64, scale=0, rounding="half_even")
        self.assertEqual(d.mul(Fixed(25, 1), Fixed(1, 0), out_scale=0), Fixed(2, 0))
        self.assertEqual(d.mul(Fixed(35, 1), Fixed(1, 0), out_scale=0), Fixed(4, 0))
        self.assertEqual(d.mul(Fixed(-25, 1), Fixed(1, 0), out_scale=0), Fixed(-2, 0))
        self.assertEqual(d.mul(Fixed(-35, 1), Fixed(1, 0), out_scale=0), Fixed(-4, 0))

    def test_negative_directions_follow_mode(self):
        cases = {
            "truncate": (-3, 3),
            "away": (-4, 4),
            "floor": (-4, 3),
            "ceil": (-3, 4),
            "half_even": (-3, 3),
        }
        for mode, (neg, pos) in cases.items():
            d = Domain(bits=64, scale=0, rounding=mode)
            # 10/3 = 3.33...
            self.assertEqual(d.div(Fixed(10, 0), Fixed(3, 0)), Fixed(pos, 0), mode)
            self.assertEqual(d.div(Fixed(-10, 0), Fixed(3, 0)), Fixed(neg, 0), mode)

    def test_upscale_is_exact_in_any_mode(self):
        for mode in MODES:
            d = Domain(bits=64, scale=0, rounding=mode)
            self.assertEqual(d.mul(Fixed(15, 1), Fixed(2, 0), out_scale=4),
                             Fixed(30000, 4))


class TestOverflowPolicies(unittest.TestCase):

    def test_default_policy_is_raise(self):
        self.assertEqual(Domain().overflow, "raise")
        with self.assertRaises(FixedPointError):
            Domain(overflow="clip")

    def test_raise_on_mul_overflow(self):
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.mul(Fixed(100, 0), Fixed(40, 0))
        with self.assertRaises(DomainOverflow):
            d.div(Fixed(-128, 0), Fixed(-1, 0))

    def test_saturate_clamps_to_bounds(self):
        d = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(d.fit(1000), 127)
        self.assertEqual(d.fit(-1000), -128)
        self.assertEqual(d.mul(Fixed(100, 0), Fixed(40, 0)), Fixed(127, 0))
        self.assertEqual(d.mul(Fixed(-100, 0), Fixed(40, 0)), Fixed(-128, 0))
        self.assertEqual(d.div(Fixed(-128, 0), Fixed(-1, 0)), Fixed(127, 0))

    def test_wrap_wraps_around(self):
        d = Domain(bits=8, scale=0, overflow="wrap")
        self.assertEqual(d.fit(128), -128)
        self.assertEqual(d.fit(129), -127)
        self.assertEqual(d.fit(-129), 127)
        # 4000 的低 8 位是 0xA0，即 -96
        self.assertEqual(d.mul(Fixed(100, 0), Fixed(40, 0)), Fixed(-96, 0))
        self.assertEqual(d.div(Fixed(-128, 0), Fixed(-1, 0)), Fixed(-128, 0))

    def test_bounds_stay_inclusive(self):
        for policy in ("raise", "saturate", "wrap"):
            d = Domain(bits=8, scale=0, overflow=policy)
            self.assertEqual(d.fit(-128), -128)
            self.assertEqual(d.fit(127), 127)
            self.assertEqual(d.mul(Fixed(127, 0), Fixed(1, 0)), Fixed(127, 0))
            self.assertEqual(d.mul(Fixed(-128, 0), Fixed(1, 0)), Fixed(-128, 0))

    def test_wide_domain_limits(self):
        d = Domain(bits=64, scale=6)
        self.assertEqual(d.fit(2 ** 63 - 1), 2 ** 63 - 1)
        self.assertEqual(d.fit(-(2 ** 63)), -(2 ** 63))
        with self.assertRaises(DomainOverflow):
            d.fit(2 ** 63)


if __name__ == "__main__":
    unittest.main()
