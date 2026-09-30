"""基线测试：锁住改造前 matpow.recur 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：
  - nth_term 按递推式从初值逐项迭代到第n项，每项之后取模；
  - prefix_sum 把逐项推出来的每一项累加后再取模，n 从零起算；
  - nth_term_nonhom 在递推式后面挂一个固定的附加常数项；
  - mat_mul 用三重循环逐项累加，mat_pow 用逐次相接连乘。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matpow.recur import (  # noqa: E402
    RecurKit,
    RecurErro,
    TermErro,
    MatrixErro,
    mat_mul,
    mat_pow,
)


MOD = 1000000007
FIB_INIT = (0, 1)
FIB_COEFF = (1, 1)


class TestNthTermBaseline(unittest.TestCase):
    def setUp(self):
        self.k = RecurKit()

    def test_fib_small_terms(self):
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 0, MOD), 0)
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 1, MOD), 1)
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 2, MOD), 1)
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 10, MOD), 55)

    def test_fib_large_term_mod(self):
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 50, MOD), 586268941)

    def test_n_below_order_returns_init(self):
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 1, MOD), 1)

    def test_order_three(self):
        init = (1, 2, 3)
        coeff = (1, 1, 1)
        self.assertEqual(self.k.nth_term(init, coeff, 3, 1000), 6)
        self.assertEqual(self.k.nth_term(init, coeff, 10, 1000), 423)

    def test_negative_coeffs_use_positive_mod(self):
        self.assertEqual(self.k.nth_term((1, 1), (-1, 1), 4, 1000), 999)
        self.assertEqual(self.k.nth_term((1, 1), (-1, 1), 7, 1000), 5)

    def test_mod_one_is_zero(self):
        self.assertEqual(self.k.nth_term(FIB_INIT, FIB_COEFF, 30, 1), 0)

    def test_iter_steps_match_linear_walk(self):
        self.k.nth_term(FIB_INIT, FIB_COEFF, 10, MOD)
        self.assertEqual(self.k.iter_steps, 9)

    def test_negative_n_raises(self):
        with self.assertRaises(TermErro):
            self.k.nth_term(FIB_INIT, FIB_COEFF, -1, MOD)

    def test_init_length_mismatch_raises(self):
        with self.assertRaises(TermErro):
            self.k.nth_term((0, 1, 2), FIB_COEFF, 5, MOD)

    def test_nonpositive_mod_raises(self):
        with self.assertRaises(TermErro):
            self.k.nth_term(FIB_INIT, FIB_COEFF, 5, 0)

    def test_term_erro_is_recur_erro(self):
        with self.assertRaises(RecurErro):
            self.k.nth_term(FIB_INIT, FIB_COEFF, -1, MOD)


class TestPrefixSumBaseline(unittest.TestCase):
    def setUp(self):
        self.k = RecurKit()

    def test_fib_prefix_small(self):
        self.assertEqual(self.k.prefix_sum(FIB_INIT, FIB_COEFF, 0, MOD), 0)
        self.assertEqual(self.k.prefix_sum(FIB_INIT, FIB_COEFF, 1, MOD), 0)
        self.assertEqual(self.k.prefix_sum(FIB_INIT, FIB_COEFF, 10, MOD), 88)

    def test_order_three_prefix(self):
        init = (1, 2, 3)
        coeff = (1, 1, 1)
        self.assertEqual(self.k.prefix_sum(init, coeff, 3, 1000), 6)
        self.assertEqual(self.k.prefix_sum(init, coeff, 10, 1000), 503)

    def test_mod_one_is_zero(self):
        self.assertEqual(self.k.prefix_sum(FIB_INIT, FIB_COEFF, 20, 1), 0)

    def test_result_in_range(self):
        total = self.k.prefix_sum(FIB_INIT, FIB_COEFF, 40, 1000)
        self.assertGreaterEqual(total, 0)
        self.assertLess(total, 1000)

    def test_negative_n_raises(self):
        with self.assertRaises(TermErro):
            self.k.prefix_sum(FIB_INIT, FIB_COEFF, -2, MOD)


class TestNonhomBaseline(unittest.TestCase):
    def setUp(self):
        self.k = RecurKit()

    def test_const_zero_matches_homogeneous(self):
        for n in range(0, 12):
            self.assertEqual(
                self.k.nth_term_nonhom(FIB_INIT, FIB_COEFF, 0, n, 1000),
                self.k.nth_term(FIB_INIT, FIB_COEFF, n, 1000))

    def test_nonzero_const(self):
        self.assertEqual(
            self.k.nth_term_nonhom(FIB_INIT, FIB_COEFF, 5, 2, 1000), 6)
        self.assertEqual(
            self.k.nth_term_nonhom(FIB_INIT, FIB_COEFF, 5, 5, 1000), 40)

    def test_iter_steps_match_linear_walk(self):
        self.k.nth_term_nonhom(FIB_INIT, FIB_COEFF, 5, 5, 1000)
        self.assertEqual(self.k.iter_steps, 4)

    def test_negative_n_raises(self):
        with self.assertRaises(TermErro):
            self.k.nth_term_nonhom(FIB_INIT, FIB_COEFF, 1, -1, 1000)


class TestMatrixBaseline(unittest.TestCase):
    A = [[1, 2], [3, 4]]

    def test_mat_mul_square(self):
        self.assertEqual(mat_mul(self.A, self.A, 1000),
                         [[7, 10], [15, 22]])

    def test_mat_mul_rectangular(self):
        self.assertEqual(mat_mul([[1, 2]], [[1], [2]], 1000), [[5]])

    def test_mat_pow_zero_is_identity(self):
        self.assertEqual(mat_pow(self.A, 0, 1000), [[1, 0], [0, 1]])

    def test_mat_pow_one_is_self(self):
        self.assertEqual(mat_pow(self.A, 1, 1000), self.A)

    def test_mat_pow_three(self):
        self.assertEqual(mat_pow(self.A, 3, 1000),
                         [[37, 54], [81, 118]])

    def test_mat_pow_mult_count_is_exponent(self):
        mat_pow(self.A, 3, 1000)
        # 朴素路径是外部计数不了内部的三重循环，这里只核对结果口径一致。
        self.assertEqual(
            mat_mul(mat_mul(self.A, self.A, 1000), self.A, 1000),
            mat_pow(self.A, 3, 1000))

    def test_shape_mismatch_raises(self):
        with self.assertRaises(MatrixErro):
            mat_mul([[1, 2, 3]], [[1, 2]], 1000)

    def test_non_square_pow_raises(self):
        with self.assertRaises(MatrixErro):
            mat_pow([[1, 2]], 2, 1000)

    def test_negative_exponent_raises(self):
        with self.assertRaises(MatrixErro):
            mat_pow(self.A, -1, 1000)

    def test_nonpositive_mod_raises(self):
        with self.assertRaises(MatrixErro):
            mat_mul(self.A, self.A, 0)

    def test_matrix_erro_is_recur_erro(self):
        self.assertTrue(issubclass(MatrixErro, RecurErro))


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        k1 = RecurKit()
        k2 = RecurKit()
        self.assertEqual(k1.nth_term(FIB_INIT, FIB_COEFF, 60, MOD),
                         k2.nth_term(FIB_INIT, FIB_COEFF, 60, MOD))
        self.assertEqual(k1.prefix_sum(FIB_INIT, FIB_COEFF, 60, MOD),
                         k2.prefix_sum(FIB_INIT, FIB_COEFF, 60, MOD))

    def test_iter_steps_reset_between_calls(self):
        k = RecurKit()
        k.nth_term(FIB_INIT, FIB_COEFF, 20, MOD)
        first = k.iter_steps
        k.nth_term(FIB_INIT, FIB_COEFF, 20, MOD)
        self.assertEqual(k.iter_steps, first)

    def test_binary_pow_int(self):
        k = RecurKit()
        self.assertEqual(k.binary_pow_int(2, 10, 1000), 24)
        self.assertEqual(k.binary_pow_int(3, 0, 7), 1)
        self.assertEqual(k.binary_pow_int(5, 3, 100), 25)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(TermErro, RecurErro))
        self.assertTrue(issubclass(RecurErro, Exception))


if __name__ == "__main__":
    unittest.main()
