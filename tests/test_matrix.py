"""基线测试：锁住改造前 detmod 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：
  - 行列式按定义递归展开与按全排列枚举两条路径，结果逐项一致；
  - 矩阵乘法用三重循环逐项累加，矩阵幂用逐次相接连乘；
  - 求逆靠伴随矩阵除以行列式，奇异矩阵如实报不可逆；
  - 解方程组用克拉默法则，系数行列式为零时报无唯一解；
  - 规模计数给出全排列项数与高斯消元操作次数；
  - 模意义下的秩与行向量线性相关判定按子式阶数给出；
  - 所有异常统一继承 DetErro 基类。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detmod.matrix import (  # noqa: E402
    DetErro,
    MatrixErro,
    ModErro,
    InverseErro,
    MatrixKit,
    egcd,
    mod_inverse,
    mat_mul,
    mat_pow,
    det_definitional,
    perm_det,
    inverse_adjugate,
    solve_cramer,
    det_terms,
    elimination_ops,
    mat_rank,
    row_rank,
    rows_dependent,
)


MOD = 1000000007
A3 = [[1, 2, 3], [4, 5, 6], [7, 8, 10]]
EYE3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


class TestDeterminantBaseline(unittest.TestCase):
    def test_two_by_two(self):
        self.assertEqual(det_definitional([[1, 2], [3, 4]], MOD), MOD - 2)
        self.assertEqual(perm_det([[1, 2], [3, 4]], MOD), MOD - 2)

    def test_three_by_three(self):
        self.assertEqual(det_definitional(A3, MOD), MOD - 3)
        self.assertEqual(perm_det(A3, MOD), MOD - 3)

    def test_two_paths_agree(self):
        for m in (
            [[5]],
            EYE3,
            [[1, 2], [2, 4]],
            [[2, 0, 1], [1, 3, 2], [1, 1, 2]],
            A3,
        ):
            self.assertEqual(det_definitional(m, MOD), perm_det(m, MOD))

    def test_singular_is_zero(self):
        self.assertEqual(det_definitional([[1, 2], [2, 4]], MOD), 0)

    def test_identity_is_one(self):
        self.assertEqual(det_definitional(EYE3, MOD), 1)

    def test_one_by_one(self):
        self.assertEqual(det_definitional([[5]], MOD), 5)

    def test_zero_matrix(self):
        self.assertEqual(det_definitional([[0, 0], [0, 0]], MOD), 0)

    def test_mod_one_all_zero(self):
        self.assertEqual(det_definitional(A3, 1), 0)

    def test_negative_entries_use_positive_mod(self):
        self.assertEqual(det_definitional([[-1, 0], [0, 1]], MOD), MOD - 1)

    def test_large_mod_big_integers(self):
        big = 10 ** 30 + 7
        self.assertEqual(det_definitional([[big, 0], [0, big]], big), 0)
        self.assertEqual(det_definitional([[big, 1], [1, big]], big + 3),
                         ((big - 1) * (big + 1)) % (big + 3))

    def test_non_square_raises(self):
        with self.assertRaises(MatrixErro):
            det_definitional([[1, 2, 3], [4, 5, 6]], MOD)

    def test_bad_mod_raises(self):
        with self.assertRaises(ModErro):
            det_definitional(A3, 0)
        with self.assertRaises(ModErro):
            det_definitional(A3, "x")


class TestInverseBaseline(unittest.TestCase):
    def test_inverse_times_original_is_identity(self):
        b = [[2, 0, 1], [1, 3, 2], [1, 1, 2]]
        inv = inverse_adjugate(b, 97)
        self.assertEqual(mat_mul(b, inv, 97), EYE3)
        self.assertEqual(mat_mul(inv, b, 97), EYE3)

    def test_two_by_two_inverse_entries(self):
        inv = inverse_adjugate([[2, 1], [1, 3]], 97)
        self.assertEqual(inv, [[20, 58], [58, 78]])

    def test_singular_raises_inverse_error(self):
        with self.assertRaises(InverseErro):
            inverse_adjugate([[1, 2], [2, 4]], 97)

    def test_non_square_raises(self):
        with self.assertRaises(MatrixErro):
            inverse_adjugate([[1, 2, 3], [4, 5, 6]], 97)

    def test_is_invertible(self):
        kit = MatrixKit()
        self.assertTrue(kit.is_invertible(A3, MOD))
        self.assertFalse(kit.is_invertible([[1, 2], [2, 4]], 97))

    def test_inverse_over_non_prime_mod_without_inverse(self):
        # 模 8 下 2 没有逆元，元素无逆元时如实报不可逆。
        with self.assertRaises(InverseErro):
            inverse_adjugate([[2, 0], [0, 1]], 8)


class TestMultiplyAndPowerBaseline(unittest.TestCase):
    def test_mat_mul_square(self):
        a = [[1, 2], [3, 4]]
        self.assertEqual(mat_mul(a, a, 1000), [[7, 10], [15, 22]])

    def test_mat_mul_shape_mismatch(self):
        with self.assertRaises(MatrixErro):
            mat_mul([[1, 2, 3]], [[1, 2]], 1000)

    def test_mat_pow_zero_is_identity(self):
        self.assertEqual(mat_pow([[1, 2], [3, 4]], 0, 1000), [[1, 0], [0, 1]])

    def test_mat_pow_three(self):
        a = [[1, 2], [3, 4]]
        self.assertEqual(mat_pow(a, 3, 1000), [[37, 54], [81, 118]])

    def test_mat_pow_negative_raises(self):
        with self.assertRaises(MatrixErro):
            mat_pow([[1, 2], [3, 4]], -1, 1000)


class TestSolveBaseline(unittest.TestCase):
    def test_unique_solution(self):
        self.assertEqual(solve_cramer([[2, 1], [1, 3]], [5, 10], 97), [1, 3])

    def test_singular_has_no_unique_solution(self):
        with self.assertRaises(InverseErro):
            solve_cramer([[1, 2], [2, 4]], [1, 2], 97)

    def test_shape_mismatch(self):
        with self.assertRaises(MatrixErro):
            solve_cramer([[1, 2], [3, 4]], [1], 97)


class TestScaleCountsBaseline(unittest.TestCase):
    def test_perm_terms_is_factorial(self):
        self.assertEqual(det_terms(0), 1)
        self.assertEqual(det_terms(1), 1)
        self.assertEqual(det_terms(5), 120)
        self.assertEqual(det_terms(6), 720)

    def test_elimination_ops(self):
        self.assertEqual(elimination_ops(0), 0)
        self.assertEqual(elimination_ops(1), 0)
        self.assertEqual(elimination_ops(6), 15)

    def test_scale_gap_grows(self):
        self.assertGreater(det_terms(8), elimination_ops(8))


class TestInverseElementBaseline(unittest.TestCase):
    def test_egcd(self):
        g, x, y = egcd(240, 46)
        self.assertEqual(g, 2)
        self.assertEqual(240 * x + 46 * y, g)

    def test_mod_inverse_prime(self):
        self.assertEqual(mod_inverse(3, 97), 65)

    def test_mod_inverse_missing_raises(self):
        with self.assertRaises(InverseErro):
            mod_inverse(4, 8)


class TestRankBaseline(unittest.TestCase):
    def test_rank_full(self):
        self.assertEqual(mat_rank(EYE3, 97), 3)

    def test_rank_deficient(self):
        self.assertEqual(mat_rank([[1, 2, 3], [4, 5, 6], [7, 8, 9]], 97), 2)

    def test_rank_zero_matrix(self):
        self.assertEqual(mat_rank([[0, 0], [0, 0]], 97), 0)

    def test_rank_rectangular(self):
        self.assertEqual(mat_rank([[1, 2, 3], [2, 4, 6]], 97), 1)

    def test_row_rank_matches_matrix_rank(self):
        rows = [[1, 2], [2, 4]]
        self.assertEqual(row_rank(rows, 97), mat_rank(rows, 97))

    def test_rows_dependent(self):
        self.assertTrue(rows_dependent([[1, 2], [2, 4]], 97))
        self.assertFalse(rows_dependent([[1, 0], [0, 1]], 97))


class TestErrorHierarchyBaseline(unittest.TestCase):
    def test_all_errors_share_base(self):
        for cls in (MatrixErro, ModErro, InverseErro):
            self.assertTrue(issubclass(cls, DetErro))

    def test_determinism(self):
        kit = MatrixKit()
        first = kit.determinant(A3, MOD)
        second = kit.determinant(A3, MOD)
        self.assertEqual(first, second)
        self.assertEqual(kit.determinant(A3, MOD), det_definitional(A3, MOD))


if __name__ == "__main__":
    unittest.main()
