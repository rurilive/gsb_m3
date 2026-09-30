"""朴素多项式乘法的现有行为锁定测试。"""

import unittest

from fftconv.conv import (
    Erro,
    IllegalArgument,
    IllegalLength,
    IllegalModulus,
    PointMismatch,
    Poly,
    check_coeffs,
    check_modulus,
    check_pointwise,
    check_transform_length,
    convolve_naive,
    evaluate_many,
    from_roots,
    is_power_of_two,
    is_prime,
    result_length,
    trim,
)


class TestCoeffs(unittest.TestCase):
    def test_accepts_ints(self):
        self.assertEqual(check_coeffs([1, 2, 3]), [1, 2, 3])

    def test_accepts_tuple(self):
        self.assertEqual(check_coeffs((0, -1)), [0, -1])

    def test_rejects_bare_string(self):
        with self.assertRaises(IllegalArgument):
            check_coeffs("abc")

    def test_rejects_float(self):
        with self.assertRaises(IllegalArgument):
            check_coeffs([1.5])

    def test_rejects_bool(self):
        with self.assertRaises(IllegalArgument):
            check_coeffs([True])


class TestTrim(unittest.TestCase):
    def test_removes_high_zeros(self):
        self.assertEqual(trim([1, 2, 0, 0]), [1, 2])

    def test_zero_polynomial_is_empty(self):
        self.assertEqual(trim([0, 0, 0]), [])

    def test_keeps_inner_zeros(self):
        self.assertEqual(trim([1, 0, 2]), [1, 0, 2])

    def test_empty_stays_empty(self):
        self.assertEqual(trim([]), [])


class TestPowerOfTwo(unittest.TestCase):
    def test_one_is_power_of_two(self):
        self.assertTrue(is_power_of_two(1))

    def test_eight_is_power_of_two(self):
        self.assertTrue(is_power_of_two(8))

    def test_six_is_not(self):
        self.assertFalse(is_power_of_two(6))

    def test_zero_is_not(self):
        self.assertFalse(is_power_of_two(0))

    def test_negative_is_not(self):
        self.assertFalse(is_power_of_two(-4))

    def test_bool_is_not(self):
        self.assertFalse(is_power_of_two(True))


class TestPrimality(unittest.TestCase):
    def test_two_is_prime(self):
        self.assertTrue(is_prime(2))

    def test_ninety_seven_is_prime(self):
        self.assertTrue(is_prime(97))

    def test_nine_is_not_prime(self):
        self.assertFalse(is_prime(9))

    def test_one_is_not_prime(self):
        self.assertFalse(is_prime(1))


class TestModulus(unittest.TestCase):
    def test_accepts_prime(self):
        self.assertEqual(check_modulus(998244353), 998244353)

    def test_rejects_composite(self):
        with self.assertRaises(IllegalModulus):
            check_modulus(12)

    def test_rejects_one(self):
        with self.assertRaises(IllegalModulus):
            check_modulus(1)


class TestTransformLength(unittest.TestCase):
    def test_accepts_power_dividing(self):
        self.assertEqual(check_transform_length(8, 998244353), 8)

    def test_rejects_non_power(self):
        with self.assertRaises(IllegalLength):
            check_transform_length(6, 998244353)

    def test_rejects_not_dividing(self):
        with self.assertRaises(IllegalLength):
            check_transform_length(16, 13)


class TestResultLength(unittest.TestCase):
    def test_both_nonempty(self):
        self.assertEqual(result_length(3, 4), 6)

    def test_empty_gives_zero(self):
        self.assertEqual(result_length(0, 5), 0)

    def test_negative_rejected(self):
        with self.assertRaises(IllegalArgument):
            result_length(-1, 2)


class TestPointwise(unittest.TestCase):
    def test_matching_lengths(self):
        xs, ys = check_pointwise([1, 2], [3, 4])
        self.assertEqual((xs, ys), ([1, 2], [3, 4]))

    def test_mismatch_rejected(self):
        with self.assertRaises(PointMismatch):
            check_pointwise([1, 2], [3])


class TestNaiveMultiply(unittest.TestCase):
    def test_constant_times_linear(self):
        p = Poly([2]).mul_naive(Poly([1, 3]))
        self.assertEqual(p.to_list(), [2, 6])

    def test_linear_times_linear(self):
        p = Poly([1, 1]).mul_naive(Poly([1, 1]))
        self.assertEqual(p.to_list(), [1, 2, 1])

    def test_zero_times_anything(self):
        p = Poly([]).mul_naive(Poly([1, 2, 3]))
        self.assertTrue(p.is_zero())

    def test_negative_coefficients(self):
        p = Poly([-1, 2]).mul_naive(Poly([3, -4]))
        self.assertEqual(p.to_list(), [-3, 10, -8])

    def test_unequal_lengths(self):
        p = Poly([1, 2, 3]).mul_naive(Poly([1, 1]))
        self.assertEqual(p.to_list(), [1, 3, 5, 3])

    def test_high_zero_dropped(self):
        p = Poly([1, 0]).mul_naive(Poly([1, 0]))
        self.assertEqual(p.to_list(), [1])

    def test_matches_convolve_naive(self):
        a = [1, 2, 3]
        b = [4, 5]
        self.assertEqual(Poly(a).mul_naive(Poly(b)).to_list(), convolve_naive(a, b))


class TestAddSub(unittest.TestCase):
    def test_add_aligns(self):
        self.assertEqual(Poly([1, 2]).add(Poly([3])).to_list(), [4, 2])

    def test_sub_aligns(self):
        self.assertEqual(Poly([5]).sub(Poly([1, 2])).to_list(), [4, -2])

    def test_add_cancels_to_zero(self):
        self.assertTrue(Poly([1, 2]).add(Poly([-1, -2])).is_zero())


class TestEvaluate(unittest.TestCase):
    def test_at_zero_is_constant(self):
        self.assertEqual(Poly([7, 3]).evaluate(0), 7)

    def test_linear_value(self):
        self.assertEqual(Poly([1, 2]).evaluate(3), 7)

    def test_zero_polynomial(self):
        self.assertEqual(Poly([]).evaluate(5), 0)

    def test_evaluate_many(self):
        self.assertEqual(evaluate_many([1, 1], [0, 1, 2]), [1, 2, 3])


class TestFromRoots(unittest.TestCase):
    def test_no_roots_is_one(self):
        self.assertEqual(from_roots([]).to_list(), [1])

    def test_single_root(self):
        self.assertEqual(from_roots([2]).to_list(), [-2, 1])

    def test_two_roots(self):
        self.assertEqual(from_roots([1, -1]).to_list(), [-1, 0, 1])


class TestReduceMod(unittest.TestCase):
    def test_normalizes_negatives(self):
        self.assertEqual(Poly([-1, 5]).reduce_mod(7).to_list(), [6, 5])

    def test_rejects_composite(self):
        with self.assertRaises(IllegalModulus):
            Poly([1]).reduce_mod(10)


class TestDegreeAndZero(unittest.TestCase):
    def test_degree_of_linear(self):
        self.assertEqual(Poly([1, 2]).degree(), 1)

    def test_degree_of_zero(self):
        self.assertEqual(Poly([]).degree(), -1)

    def test_equality(self):
        self.assertEqual(Poly([1, 2, 0]), Poly([1, 2]))


class TestErrorHierarchy(unittest.TestCase):
    def test_illegal_argument_is_erro(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))

    def test_illegal_length_is_erro(self):
        self.assertTrue(issubclass(IllegalLength, Erro))

    def test_illegal_modulus_is_erro(self):
        self.assertTrue(issubclass(IllegalModulus, Erro))

    def test_point_mismatch_is_erro(self):
        self.assertTrue(issubclass(PointMismatch, Erro))

    def test_erro_is_exception(self):
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
