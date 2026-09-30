"""modarith 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：朴素模幂、逐个试乘求逆元、
枚举解同余方程、先算阶乘再相除的组合数、逐个区间合并的中国剩余定理，
以及异常层级与几处边界。改造时本文件一个字都不许改，
新行为一律另开测试文件。
"""

import unittest

from modarith.modarith import (
    InverseNotExistsError,
    InvalidCombinationError,
    InvalidModulusError,
    ModarithError,
    NegativeExponentError,
    NoSolutionError,
    NotCoprimeError,
    comb_mod,
    crt,
    mod_inverse,
    mod_pow,
    solve_linear_congruence,
)


class TestModPow(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(mod_pow(3, 4, 10), 1)

    def test_small(self):
        self.assertEqual(mod_pow(2, 10, 1000), 24)

    def test_exponent_zero_is_one(self):
        self.assertEqual(mod_pow(7, 0, 13), 1)

    def test_modulus_two(self):
        self.assertEqual(mod_pow(5, 3, 2), 1)

    def test_base_larger_than_mod(self):
        self.assertEqual(mod_pow(100, 2, 7), 4)

    def test_negative_exponent_raises(self):
        with self.assertRaises(NegativeExponentError):
            mod_pow(2, -1, 7)

    def test_bad_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            mod_pow(2, 3, 1)


class TestModInverse(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(mod_inverse(3, 7), 5)

    def test_product_is_one(self):
        self.assertEqual((3 * mod_inverse(3, 11)) % 11, 1)

    def test_one(self):
        self.assertEqual(mod_inverse(1, 13), 1)

    def test_not_coprime_raises(self):
        with self.assertRaises(InverseNotExistsError):
            mod_inverse(4, 8)

    def test_bad_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            mod_inverse(3, 1)


class TestSolveLinearCongruence(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(solve_linear_congruence(3, 1, 7), 5)

    def test_solution_satisfies(self):
        x = solve_linear_congruence(4, 2, 6)
        self.assertEqual((4 * x - 2) % 6, 0)

    def test_no_solution_raises(self):
        with self.assertRaises(NoSolutionError):
            solve_linear_congruence(2, 1, 4)

    def test_bad_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            solve_linear_congruence(2, 1, 0)


class TestCombMod(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(comb_mod(5, 2, 1000), 10)

    def test_choose_n(self):
        self.assertEqual(comb_mod(6, 6, 1000), 1)

    def test_choose_zero(self):
        self.assertEqual(comb_mod(6, 0, 1000), 1)

    def test_choose_one(self):
        self.assertEqual(comb_mod(10, 1, 1000), 10)

    def test_k_greater_than_n_raises(self):
        with self.assertRaises(InvalidCombinationError):
            comb_mod(3, 5, 1000)

    def test_negative_raises(self):
        with self.assertRaises(InvalidCombinationError):
            comb_mod(-1, 2, 1000)

    def test_bad_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            comb_mod(5, 2, 1)


class TestCrt(unittest.TestCase):
    def test_single(self):
        self.assertEqual(crt([2], [5]), 2)

    def test_two_coprime(self):
        result = crt([2, 3], [3, 5])
        self.assertEqual(result % 3, 2)
        self.assertEqual(result % 5, 3)

    def test_three_coprime(self):
        result = crt([1, 2, 3], [3, 5, 7])
        self.assertEqual(result % 3, 1)
        self.assertEqual(result % 5, 2)
        self.assertEqual(result % 7, 3)

    def test_not_coprime_raises(self):
        with self.assertRaises(NotCoprimeError):
            crt([1, 2], [4, 6])

    def test_length_mismatch_raises(self):
        with self.assertRaises(ModarithError):
            crt([1, 2], [3])


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_derive_from_base(self):
        for exc in (
            InvalidModulusError,
            NegativeExponentError,
            InverseNotExistsError,
            NoSolutionError,
            NotCoprimeError,
            InvalidCombinationError,
        ):
            self.assertTrue(issubclass(exc, ModarithError))

    def test_base_is_exception(self):
        self.assertTrue(issubclass(ModarithError, Exception))


if __name__ == "__main__":
    unittest.main()
