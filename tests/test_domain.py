"""Domain 行为基线：配置校验、域宽收口、域内运算与精度落定。"""

import unittest

from fixedpt import Domain, DomainOverflow, Fixed, FixedPointError


class TestConfig(unittest.TestCase):

    def test_defaults(self):
        d = Domain()
        self.assertEqual(d.bits, 64)
        self.assertEqual(d.scale, 6)
        self.assertEqual(d.overflow, "raise")
        self.assertEqual(d.min_unscaled, -(2 ** 63))
        self.assertEqual(d.max_unscaled, 2 ** 63 - 1)

    def test_rejects_bad_config(self):
        with self.assertRaises(FixedPointError):
            Domain(bits=1)
        with self.assertRaises(FixedPointError):
            Domain(scale=-1)
        with self.assertRaises(FixedPointError):
            Domain(overflow="clip")


class TestFit(unittest.TestCase):

    def test_bounds_are_inclusive(self):
        d = Domain(bits=8, scale=0)
        self.assertEqual(d.fit(-128), -128)
        self.assertEqual(d.fit(127), 127)

    def test_out_of_bounds_raises(self):
        d = Domain(bits=8, scale=0)
        with self.assertRaises(DomainOverflow):
            d.fit(128)
        with self.assertRaises(DomainOverflow):
            d.fit(-129)

    def test_fixed_factory(self):
        d = Domain(bits=32, scale=2)
        v = d.fixed(325)
        self.assertEqual((v.unscaled, v.scale), (325, 2))
        self.assertEqual(d.fixed(5, scale=0).scale, 0)
        with self.assertRaises(DomainOverflow):
            d.fixed(2 ** 31)


class TestDomainOps(unittest.TestCase):

    def test_add_sub_fit_results(self):
        d = Domain(bits=8, scale=0)
        self.assertEqual(d.add(Fixed(100, 0), Fixed(27, 0)), Fixed(127, 0))
        self.assertEqual(d.sub(Fixed(30, 0), Fixed(-40, 0)), Fixed(70, 0))
        with self.assertRaises(DomainOverflow):
            d.add(Fixed(100, 0), Fixed(28, 0))
        with self.assertRaises(DomainOverflow):
            d.sub(Fixed(-100, 0), Fixed(29, 0))

    def test_mul_lands_on_out_scale(self):
        d = Domain(bits=64, scale=6)
        amount = d.fixed(10_500_000)       # 10.50
        rate = Fixed(250_000, 6)           # 0.250000
        self.assertEqual(d.mul(amount, rate, out_scale=2), Fixed(262, 2))

    def test_div_lands_on_out_scale(self):
        d = Domain(bits=64, scale=6)
        self.assertEqual(
            d.div(d.fixed(10_500_000), Fixed(4, 0), out_scale=2), Fixed(262, 2))

    def test_div_by_zero(self):
        d = Domain(bits=64, scale=6)
        with self.assertRaises(ZeroDivisionError):
            d.div(d.fixed(100), Fixed(0, 0))


if __name__ == "__main__":
    unittest.main()
