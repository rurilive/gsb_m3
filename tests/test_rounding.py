"""五种舍入模式的整数原语、Fixed 裁剪与 Domain 乘除舍入。"""

import unittest

from fixedpt import CEIL, FLOOR, HALF_EVEN, TRUNC, UP, Domain, Fixed
from fixedpt.rounding import div_round, div_trunc, rescale


class TestDivTrunc(unittest.TestCase):

    def test_positive_is_floor(self):
        self.assertEqual(div_trunc(7, 2), 3)
        self.assertEqual(div_trunc(8, 2), 4)

    def test_negative_heads_toward_zero(self):
        self.assertEqual(div_trunc(-7, 2), -3)
        self.assertEqual(div_trunc(7, -2), -3)
        self.assertEqual(div_trunc(-7, -2), 3)
        self.assertEqual(div_trunc(-1, 3), 0)

    def test_zero(self):
        self.assertEqual(div_trunc(0, 7), 0)

    def test_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            div_trunc(1, 0)


class TestDivRoundModes(unittest.TestCase):

    def test_exact_quotient_never_moves(self):
        for mode in (TRUNC, HALF_EVEN, UP, FLOOR, CEIL):
            self.assertEqual(div_round(8, 2, mode), 4)
            self.assertEqual(div_round(-8, 2, mode), -4)
            self.assertEqual(div_round(0, 3, mode), 0)

    def test_trunc_moves_toward_zero(self):
        self.assertEqual(div_round(7, 2, TRUNC), 3)
        self.assertEqual(div_round(-7, 2, TRUNC), -3)

    def test_up_moves_away_from_zero(self):
        self.assertEqual(div_round(7, 2, UP), 4)
        self.assertEqual(div_round(-7, 2, UP), -4)
        self.assertEqual(div_round(1, 100, UP), 1)
        self.assertEqual(div_round(-1, 100, UP), -1)

    def test_floor_moves_toward_negative_infinity(self):
        self.assertEqual(div_round(7, 2, FLOOR), 3)
        self.assertEqual(div_round(-7, 2, FLOOR), -4)

    def test_ceil_moves_toward_positive_infinity(self):
        self.assertEqual(div_round(7, 2, CEIL), 4)
        self.assertEqual(div_round(-7, 2, CEIL), -3)

    def test_half_even_tie_to_even(self):
        cases = {
            (5, 2): 2, (-5, 2): -2,
            (7, 2): 4, (-7, 2): -4,
            (15, 10): 2, (-15, 10): -2,
            (25, 10): 2, (-25, 10): -2,
            (35, 10): 4, (-35, 10): -4,
        }
        for (num, den), want in cases.items():
            self.assertEqual(div_round(num, den, HALF_EVEN), want, (num, den))

    def test_half_even_non_ties(self):
        self.assertEqual(div_round(24, 10, HALF_EVEN), 2)
        self.assertEqual(div_round(26, 10, HALF_EVEN), 3)
        self.assertEqual(div_round(-24, 10, HALF_EVEN), -2)
        self.assertEqual(div_round(-26, 10, HALF_EVEN), -3)

    def test_negative_denominator_matches_sign_normalization(self):
        for mode in (TRUNC, HALF_EVEN, UP, FLOOR, CEIL):
            self.assertEqual(
                div_round(7, 2, mode), div_round(-7, -2, mode))
            self.assertEqual(
                div_round(-7, 2, mode), div_round(7, -2, mode))

    def test_unknown_mode_rejected(self):
        from fixedpt import FixedPointError
        with self.assertRaises(FixedPointError):
            div_round(1, 2, "banker")


class TestRescale(unittest.TestCase):

    def test_identity_and_trunc(self):
        self.assertEqual(rescale(1234, 1, TRUNC), 1234)
        self.assertEqual(rescale(1234, 10, TRUNC), 123)
        self.assertEqual(rescale(-1234, 10, TRUNC), -123)

    def test_half_even_by_decimal_factor(self):
        self.assertEqual(rescale(125, 10, HALF_EVEN), 12)
        self.assertEqual(rescale(135, 10, HALF_EVEN), 14)
        self.assertEqual(rescale(-125, 10, HALF_EVEN), -12)
        self.assertEqual(rescale(-135, 10, HALF_EVEN), -14)
        self.assertEqual(rescale(250, 100, HALF_EVEN), 2)


class TestFixedRescaledNegativeTrunc(unittest.TestCase):
    """Fixed 层降精度的朝零截断对负数同样成立（默认口径不变）。"""

    def test_negative_downscale_toward_zero(self):
        self.assertEqual(Fixed(-129, 2).rescaled(1), Fixed(-12, 1))
        self.assertEqual(Fixed(-125, 2).rescaled(1), Fixed(-12, 1))


class TestDomainRoundingConfig(unittest.TestCase):

    def test_default_rounding_is_trunc(self):
        self.assertEqual(Domain().rounding, TRUNC)

    def test_domain_rounding_modes_on_div(self):
        d = Domain(bits=64, scale=2)
        # 2.50 / 1 = 2.50，正好落在 scale=2 下 2.50 与 2.51 的半上
        a, b = Fixed(2505, 3), Fixed(1, 0)
        want = {
            TRUNC: (250, -250),
            HALF_EVEN: (250, -250),
            UP: (251, -251),
            FLOOR: (250, -251),
            CEIL: (251, -250),
        }
        for mode, (pos, neg) in want.items():
            self.assertEqual(d.div(a, b, out_scale=2, rounding=mode), Fixed(pos, 2), mode)
            self.assertEqual(d.div(-a, b, out_scale=2, rounding=mode), Fixed(neg, 2), mode)

    def test_domain_rounding_modes_on_mul(self):
        d = Domain(bits=64, scale=2)
        # 2.505 * 1 = 2.505，落 scale=2 是 2.50 与 2.51 正中
        a, b = Fixed(2505, 3), Fixed(1, 0)
        want = {
            TRUNC: (250, -250),
            HALF_EVEN: (250, -250),
            UP: (251, -251),
            FLOOR: (250, -251),
            CEIL: (251, -250),
        }
        for mode, (pos, neg) in want.items():
            self.assertEqual(d.mul(a, b, out_scale=2, rounding=mode),
                             Fixed(pos, 2), mode)
            self.assertEqual(d.mul(-a, b, out_scale=2, rounding=mode),
                             Fixed(neg, 2), mode)

    def test_domain_level_default_mode_applied(self):
        d = Domain(bits=64, scale=2, rounding=HALF_EVEN)
        # 2.515 落 scale=2，half_even 靠向偶数 2.52
        self.assertEqual(
            d.div(Fixed(2515, 3), Fixed(1, 0), out_scale=2), Fixed(252, 2))
        self.assertEqual(
            d.div(Fixed(2505, 3), Fixed(1, 0), out_scale=2), Fixed(250, 2))

    def test_zero_results_are_zero_in_every_mode(self):
        d = Domain(bits=64, scale=2)
        for mode in (TRUNC, HALF_EVEN, UP, FLOOR, CEIL):
            self.assertEqual(
                d.mul(Fixed(0, 4), Fixed(7, 0), rounding=mode), Fixed(0, 2))
            self.assertEqual(
                d.div(Fixed(0, 4), Fixed(7, 0), rounding=mode), Fixed(0, 2))


if __name__ == "__main__":
    unittest.main()
