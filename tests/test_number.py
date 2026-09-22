"""Fixed 行为基线：构造、对齐比较、精确加减、定标乘除与降精度裁剪。"""

import unittest

from fixedpt import Fixed, FixedPointError


class TestConstruction(unittest.TestCase):

    def test_unscaled_must_be_int(self):
        with self.assertRaises(FixedPointError):
            Fixed(1.5, 2)
        with self.assertRaises(FixedPointError):
            Fixed("12", 2)

    def test_scale_must_be_non_negative_int(self):
        with self.assertRaises(FixedPointError):
            Fixed(1, -1)
        with self.assertRaises(FixedPointError):
            Fixed(1, 1.5)

    def test_readers_and_sign(self):
        v = Fixed(-12345, 3)
        self.assertEqual(v.unscaled, -12345)
        self.assertEqual(v.scale, 3)
        self.assertEqual(v.sign(), -1)
        self.assertEqual(Fixed(0, 2).sign(), 0)
        self.assertEqual(Fixed(7, 1).sign(), 1)
        self.assertFalse(Fixed(0, 2))
        self.assertTrue(Fixed(1, 6))
        self.assertTrue(Fixed(0, 2).is_zero())

    def test_repr(self):
        self.assertEqual(repr(Fixed(12, 2)), "Fixed(unscaled=12, scale=2)")


class TestAlignAndCompare(unittest.TestCase):

    def test_add_aligns_to_larger_scale(self):
        self.assertEqual(Fixed(120, 2) + Fixed(3, 0), Fixed(420, 2))
        self.assertEqual(Fixed(5, 1) - Fixed(25, 2), Fixed(25, 2))
        self.assertEqual((Fixed(1, 0) + Fixed(1, 3)).scale, 3)

    def test_neg_and_abs(self):
        self.assertEqual(-Fixed(7, 2), Fixed(-7, 2))
        self.assertEqual(abs(Fixed(-7, 2)), Fixed(7, 2))
        self.assertEqual(abs(Fixed(7, 2)), Fixed(7, 2))

    def test_cross_scale_equality(self):
        self.assertEqual(Fixed(120, 2), Fixed(12, 1))
        self.assertNotEqual(Fixed(120, 2), Fixed(121, 2))

    def test_ordering(self):
        self.assertTrue(Fixed(5, 1) < Fixed(51, 2))
        self.assertTrue(Fixed(-2, 0) <= Fixed(-15, 1))
        self.assertTrue(Fixed(-15, 1) > Fixed(-2, 0))
        self.assertTrue(Fixed(3, 0) >= Fixed(299, 2))

    def test_equal_values_hash_alike(self):
        self.assertEqual(hash(Fixed(120, 2)), hash(Fixed(12, 1)))
        self.assertEqual(len({Fixed(120, 2), Fixed(12, 1)}), 1)


class TestRescale(unittest.TestCase):

    def test_up_is_exact(self):
        self.assertEqual(Fixed(3, 1).rescaled(3), Fixed(300, 3))

    def test_down_drops_low_digits(self):
        self.assertEqual(Fixed(1234, 3).rescaled(2), Fixed(123, 2))
        self.assertEqual(Fixed(1299, 3).rescaled(2), Fixed(129, 2))

    def test_same_scale_is_identity(self):
        self.assertEqual(Fixed(7, 4).rescaled(4), Fixed(7, 4))


class TestMulDiv(unittest.TestCase):

    def test_mul_lands_on_larger_scale(self):
        self.assertEqual(Fixed(250, 2).mul(Fixed(4, 0)), Fixed(1000, 2))
        # 0.25 * 0.4 = 0.10
        self.assertEqual(Fixed(25, 2).mul(Fixed(4, 1)), Fixed(10, 2))
        self.assertEqual(Fixed(25, 2).mul(Fixed(4, 1), out_scale=3), Fixed(100, 3))

    def test_mul_drops_low_digits(self):
        # 1.234 * 1.0 精确是 1.234，落到 scale=2 是 1.23
        self.assertEqual(Fixed(1234, 3).mul(Fixed(10, 1), out_scale=2), Fixed(123, 2))

    def test_div_lands_on_out_scale(self):
        self.assertEqual(Fixed(100, 2).div(Fixed(4, 0)), Fixed(25, 2))
        self.assertEqual(Fixed(7, 0).div(Fixed(2, 0)), Fixed(3, 0))
        self.assertEqual(Fixed(1, 0).div(Fixed(8, 0), out_scale=3), Fixed(125, 3))

    def test_div_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            Fixed(1, 0).div(Fixed(0, 0))

    def test_operators(self):
        self.assertEqual(Fixed(15, 1) * Fixed(2, 0), Fixed(30, 1))
        self.assertEqual(Fixed(15, 1) / Fixed(3, 0), Fixed(5, 1))


if __name__ == "__main__":
    unittest.main()
