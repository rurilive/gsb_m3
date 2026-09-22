"""乘除的域收口：raise（默认安全档）、saturate、wrap。"""

import unittest

from fixedpt import (
    CEIL,
    Domain,
    DomainOverflow,
    Fixed,
    FixedPointError,
    FLOOR,
    HALF_EVEN,
)


class TestPolicyConfig(unittest.TestCase):

    def test_default_is_raise(self):
        self.assertEqual(Domain().overflow, "raise")

    def test_unknown_policy_rejected(self):
        with self.assertRaises(FixedPointError):
            Domain(overflow="clip")
        with self.assertRaises(FixedPointError):
            Domain(overflow="wrapping")


class TestFitPolicies(unittest.TestCase):

    def test_wrap_is_twos_complement(self):
        d = Domain(bits=8, scale=0, overflow="wrap")
        self.assertEqual(d.fit(127), 127)
        self.assertEqual(d.fit(128), -128)
        self.assertEqual(d.fit(129), -127)
        self.assertEqual(d.fit(255), -1)
        self.assertEqual(d.fit(256), 0)
        self.assertEqual(d.fit(-129), 127)
        self.assertEqual(d.fit(-256), 0)
        self.assertEqual(d.fit(300), 44)
        self.assertEqual(d.fit(-300), -44)

    def test_saturate_clamps_to_bounds(self):
        d = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(d.fit(127), 127)
        self.assertEqual(d.fit(128), 127)
        self.assertEqual(d.fit(10 ** 9), 127)
        self.assertEqual(d.fit(-129), -128)
        self.assertEqual(d.fit(-10 ** 9), -128)

    def test_raise_keeps_safe_default(self):
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.fit(128)
        with self.assertRaises(DomainOverflow):
            d.fit(-129)


class TestMulDivFit(unittest.TestCase):

    def test_mul_fits_after_scaling_raise(self):
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.mul(Fixed(100, 0), Fixed(40, 0))
        with self.assertRaises(DomainOverflow):
            d.mul(Fixed(-100, 0), Fixed(40, 0))

    def test_div_fits_after_scaling_raise(self):
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.div(Fixed(1000, 0), Fixed(1, 0))

    def test_mul_saturate(self):
        d = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(d.mul(Fixed(100, 0), Fixed(40, 0)), Fixed(127, 0))
        self.assertEqual(d.mul(Fixed(-100, 0), Fixed(40, 0)), Fixed(-128, 0))

    def test_div_saturate(self):
        d = Domain(bits=8, scale=0, overflow="saturate")
        self.assertEqual(d.div(Fixed(1000, 0), Fixed(1, 0)), Fixed(127, 0))
        self.assertEqual(d.div(Fixed(-1000, 0), Fixed(1, 0)), Fixed(-128, 0))

    def test_mul_wrap(self):
        d = Domain(bits=8, scale=0, overflow="wrap")
        self.assertEqual(d.mul(Fixed(100, 0), Fixed(40, 0)), Fixed(-96, 0))

    def test_in_domain_results_unchanged_by_policy(self):
        for policy in ("raise", "saturate", "wrap"):
            d = Domain(bits=8, scale=0, overflow=policy)
            self.assertEqual(d.mul(Fixed(5, 0), Fixed(7, 0)), Fixed(35, 0))
            self.assertEqual(d.div(Fixed(-35, 0), Fixed(7, 0)), Fixed(-5, 0))

    def test_rounding_happens_before_fit(self):
        # 1.275 * 100 = 127.5，half_even 先舍到 128（再按策略处理），
        # trunc 先裁到 127（留在域内）。
        d_raise = Domain(bits=8, scale=0, rounding=HALF_EVEN)
        with self.assertRaises(DomainOverflow):
            d_raise.mul(Fixed(1275, 3), Fixed(100, 0), out_scale=0)
        d_sat = Domain(bits=8, scale=0, overflow="saturate",
                       rounding=HALF_EVEN)
        self.assertEqual(d_sat.mul(Fixed(1275, 3), Fixed(100, 0), out_scale=0),
                         Fixed(127, 0))
        d_trunc = Domain(bits=8, scale=0)
        self.assertEqual(d_trunc.mul(Fixed(1275, 3), Fixed(100, 0), out_scale=0),
                         Fixed(127, 0))

    def test_negative_half_at_lower_bound_floor_saturates(self):
        d = Domain(bits=8, scale=0, overflow="saturate", rounding=FLOOR)
        # -127.5 floor 到 -128，恰好是下界，不触发饱和
        self.assertEqual(d.mul(Fixed(-1275, 3), Fixed(100, 0), out_scale=0),
                         Fixed(-128, 0))
        # -128.5 floor 到 -129，夹到 -128
        self.assertEqual(d.mul(Fixed(-1285, 3), Fixed(100, 0), out_scale=0),
                         Fixed(-128, 0))


if __name__ == "__main__":
    unittest.main()
