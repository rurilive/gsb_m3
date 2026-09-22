"""边界与极限：域宽端点、最小/最大乘积、舍入边界、scale=0 与大位宽。"""

import time
import unittest

from fixedpt import CEIL, FLOOR, HALF_EVEN, TRUNC, UP, Domain, Fixed


class TestDomainBounds(unittest.TestCase):

    def test_mul_div_at_64_bit_edges(self):
        d = Domain(bits=64, scale=0)
        hi, lo = 2 ** 63 - 1, -(2 ** 63)
        self.assertEqual(d.mul(Fixed(hi, 0), Fixed(1, 0)), Fixed(hi, 0))
        self.assertEqual(d.mul(Fixed(lo, 0), Fixed(1, 0)), Fixed(lo, 0))
        self.assertEqual(d.div(Fixed(hi, 0), Fixed(1, 0)), Fixed(hi, 0))
        self.assertEqual(d.div(Fixed(lo, 0), Fixed(1, 0)), Fixed(lo, 0))

    def test_one_beyond_edge_raises(self):
        d = Domain(bits=64, scale=0)
        with self.assertRaises(Exception):
            d.mul(Fixed(2 ** 63, 0), Fixed(1, 0))
        with self.assertRaises(Exception):
            d.div(Fixed(-(2 ** 63) - 1, 0), Fixed(1, 0))

    def test_wrap_edges_under_all_modes(self):
        d = Domain(bits=8, scale=0, overflow="wrap")
        for mode in (TRUNC, HALF_EVEN, UP, FLOOR, CEIL):
            # 128 在 8 位补码下回绕到 -128
            self.assertEqual(
                d.mul(Fixed(16, 0), Fixed(8, 0), rounding=mode),
                Fixed(-128, 0), mode)
            self.assertEqual(
                d.mul(Fixed(-16, 0), Fixed(8, 0), rounding=mode),
                Fixed(-128, 0), mode)
            self.assertEqual(
                d.mul(Fixed(32, 0), Fixed(8, 0), rounding=mode),
                Fixed(0, 0), mode)

    def test_saturate_endpoints_preferred(self):
        d = Domain(bits=8, scale=0, overflow="saturate")
        # 结果正好落在端点上时不被改变
        self.assertEqual(d.div(Fixed(127, 0), Fixed(1, 0)), Fixed(127, 0))
        self.assertEqual(d.div(Fixed(-128, 0), Fixed(1, 0)), Fixed(-128, 0))


class TestRoundingBoundaries(unittest.TestCase):

    def test_exact_half_at_every_digit(self):
        d = Domain(bits=256, scale=0)
        for digits in range(1, 8):
            unit = 10 ** digits
            half = unit // 2
            for base in range(-3, 4):
                num = base * unit + half
                got = d.div(Fixed(num, digits), Fixed(1, 0),
                            out_scale=0,
                            rounding=HALF_EVEN)
                # num/unit = base + 0.5，half_even 取偶
                want = base if base % 2 == 0 else base + 1
                self.assertEqual(got, Fixed(want, 0), (digits, base, num))

    def test_ulp_away_from_tie(self):
        d = Domain(bits=256, scale=0)
        # 1.4999... 与 1.5000...1 在 half_even 下分居两侧
        for delta, want in ((-1, 1), (1, 2)):
            num = 15_000_000 + delta
            self.assertEqual(
                d.div(Fixed(num, 7), Fixed(1, 0), out_scale=0,
                      rounding=HALF_EVEN),
                Fixed(want, 0), delta)

    def test_negative_symmetry(self):
        # trunc / half_even 对正负有对称性，floor/ceil 互换、up 对称
        d = Domain(bits=256, scale=1)
        for num in range(-99, 100):
            a = Fixed(num, 2)
            self.assertEqual(
                d.div(-a, Fixed(1, 0), out_scale=1, rounding=HALF_EVEN),
                -d.div(a, Fixed(1, 0), out_scale=1, rounding=HALF_EVEN), num)
            self.assertEqual(
                d.div(-a, Fixed(1, 0), out_scale=1, rounding=TRUNC),
                -d.div(a, Fixed(1, 0), out_scale=1, rounding=TRUNC), num)
            self.assertEqual(
                d.div(-a, Fixed(1, 0), out_scale=1, rounding=UP),
                -d.div(a, Fixed(1, 0), out_scale=1, rounding=UP), num)
            self.assertEqual(
                d.div(-a, Fixed(1, 0), out_scale=1, rounding=FLOOR),
                -d.div(a, Fixed(1, 0), out_scale=1, rounding=CEIL), num)


class TestScaleEdges(unittest.TestCase):

    def test_scale_zero_domain(self):
        d = Domain(bits=16, scale=0)
        self.assertEqual(d.mul(Fixed(7, 0), Fixed(9, 0)), Fixed(63, 0))
        self.assertEqual(d.div(Fixed(7, 0), Fixed(2, 0)), Fixed(3, 0))
        self.assertEqual(d.div(Fixed(7, 0), Fixed(2, 0), rounding=HALF_EVEN),
                         Fixed(4, 0))
        self.assertEqual(d.parse("42"), Fixed(42, 0))
        self.assertEqual(d.text(Fixed(42, 0)), "42")

    def test_out_scale_zero_keeps_fraction_sign_direction(self):
        d = Domain(bits=64, scale=0)
        a = Fixed(-25, 1)            # -2.5
        self.assertEqual(d.div(a, Fixed(1, 0), out_scale=0,
                               rounding=HALF_EVEN), Fixed(-2, 0))
        self.assertEqual(d.div(a, Fixed(1, 0), out_scale=0,
                               rounding=UP), Fixed(-3, 0))

    def test_out_scale_higher_than_inputs_is_exact(self):
        d = Domain(bits=64, scale=6)
        # 0.01 * 0.01 = 0.0001
        self.assertEqual(
            d.mul(Fixed(1, 2), Fixed(1, 2), out_scale=6), Fixed(100, 6))
        self.assertEqual(
            d.div(Fixed(1, 0), Fixed(8, 0), out_scale=6), Fixed(125000, 6))


class TestExtremeValues(unittest.TestCase):

    def test_large_wide_domain_product(self):
        d = Domain(bits=512, scale=18)
        a = Fixed(10 ** 30 - 1, 18)
        b = Fixed(10 ** 20, 18)
        got = d.mul(a, b, out_scale=18, rounding=HALF_EVEN)
        self.assertEqual(got.unscaled, (10 ** 30 - 1) * 10 ** 2)

    def test_huge_exponent_parse_and_text(self):
        d = Domain(bits=1024, scale=6)
        value = d.parse("9.999999e100")
        self.assertEqual(value.unscaled, 9_999_999 * 10 ** 100)
        self.assertTrue(d.text(value).startswith("9999999"))

    def test_saturate_absorbs_extreme_product(self):
        d = Domain(bits=64, scale=0, overflow="saturate")
        self.assertEqual(
            d.mul(Fixed(10 ** 30, 0), Fixed(10 ** 30, 0)),
            Fixed(2 ** 63 - 1, 0))
        self.assertEqual(
            d.mul(Fixed(-10 ** 30, 0), Fixed(10 ** 30, 0)),
            Fixed(-(2 ** 63), 0))


class TestMillionOpsPerformance(unittest.TestCase):

    def test_million_mul_div_under_15_seconds(self):
        d = Domain(bits=64, scale=6, rounding=HALF_EVEN)
        a = Fixed(123_456_789, 6)
        b = Fixed(987_654, 6)
        start = time.perf_counter()
        count = 1_000_000
        for _ in range(count):
            d.mul(a, b, out_scale=6)
            d.div(a, b, out_scale=6)
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 15.0,
            "%d mul+div pairs took %.2fs" % (count, elapsed))


if __name__ == "__main__":
    unittest.main()
