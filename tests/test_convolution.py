"""改造前基线的现状行为测试。"""

import unittest

from subsetconv import (
    ConvolutionError,
    InvalidLengthError,
    LengthMismatchError,
    SetFunction,
    is_power_of_two,
)
from subsetconv.convolution import SetFunction as SF


def brute_or(a, b):
    n = len(a)
    out = [0] * n
    for i in range(n):
        for j in range(n):
            out[i | j] += a[i] * b[j]
    return out


def brute_and(a, b):
    n = len(a)
    out = [0] * n
    for i in range(n):
        for j in range(n):
            out[i & j] += a[i] * b[j]
    return out


def brute_xor(a, b):
    n = len(a)
    out = [0] * n
    for i in range(n):
        for j in range(n):
            out[i ^ j] += a[i] * b[j]
    return out


def brute_subset(a, b):
    n = len(a)
    out = [0] * n
    for i in range(n):
        for j in range(n):
            if (i & j) == 0:
                out[i | j] += a[i] * b[j]
    return out


class TestLengthValidation(unittest.TestCase):
    def test_power_of_two_predicate(self):
        for n in (1, 2, 4, 8, 16):
            self.assertTrue(is_power_of_two(n))
        for n in (0, -1, -4, 3, 6, 7, 12):
            self.assertFalse(is_power_of_two(n))

    def test_reject_non_power_of_two(self):
        for bad in ([], [1, 2, 3], [0] * 6):
            with self.assertRaises(InvalidLengthError):
                SetFunction(bad)

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(InvalidLengthError, ConvolutionError))
        self.assertTrue(issubclass(LengthMismatchError, ConvolutionError))
        self.assertTrue(issubclass(ConvolutionError, Exception))

    def test_len_one_is_valid(self):
        sf = SetFunction([7])
        self.assertEqual(len(sf), 1)
        self.assertEqual(sf.size, 1)
        self.assertEqual(sf.pair_count(), 1)

    def test_mismatch_raises(self):
        a = SetFunction([1, 2, 3, 4])
        b = SetFunction([1, 2])
        for fn in ("or_convolve", "and_convolve", "xor_convolve",
                   "subset_convolve"):
            with self.assertRaises(LengthMismatchError):
                getattr(a, fn)(b)

    def test_bad_partner_type(self):
        a = SetFunction([1, 2])
        with self.assertRaises(ConvolutionError):
            a.or_convolve([1, 2])


class TestOrConvolution(unittest.TestCase):
    def test_matches_brute(self):
        a = [1, 2, 3, 4]
        b = [5, 6, 7, 8]
        self.assertEqual(SetFunction(a).or_convolve(SF(b)).as_list(),
                         brute_or(a, b))

    def test_or_known_result(self):
        a = [1, 2, 0, 0]
        b = [1, 0, 3, 0]
        # 单点集合 {0} 与 {1} 的或落到 {0,1} 下标 3
        self.assertEqual(SetFunction(a).or_convolve(SF(b)).as_list(),
                         [1, 2, 3, 6])


class TestAndConvolution(unittest.TestCase):
    def test_matches_brute(self):
        a = [1, 2, 3, 4]
        b = [5, 6, 7, 8]
        self.assertEqual(SetFunction(a).and_convolve(SF(b)).as_list(),
                         brute_and(a, b))

    def test_and_known_result(self):
        a = [0, 0, 3, 4]
        b = [0, 0, 3, 5]
        self.assertEqual(SetFunction(a).and_convolve(SF(b)).as_list(),
                         brute_and(a, b))


class TestXorConvolution(unittest.TestCase):
    def test_matches_brute(self):
        a = [1, 2, 3, 4]
        b = [5, 6, 7, 8]
        self.assertEqual(SetFunction(a).xor_convolve(SF(b)).as_list(),
                         brute_xor(a, b))

    def test_single_element_all_ops_equal(self):
        # 长度为一退化成标量乘法，四种卷积结果一致
        a = [6]
        b = [7]
        fa = SetFunction(a)
        fb = SF(b)
        self.assertEqual(fa.or_convolve(fb).as_list(), [42])
        self.assertEqual(fa.and_convolve(fb).as_list(), [42])
        self.assertEqual(fa.xor_convolve(fb).as_list(), [42])
        self.assertEqual(fa.subset_convolve(fb).as_list(), [42])


class TestSubsetConvolution(unittest.TestCase):
    def test_matches_brute(self):
        a = [1, 2, 3, 4]
        b = [5, 6, 7, 8]
        self.assertEqual(SetFunction(a).subset_convolve(SF(b)).as_list(),
                         brute_subset(a, b))

    def test_disjoint_only(self):
        a = [1, 2, 4, 8]
        b = [1, 2, 4, 8]
        self.assertEqual(SetFunction(a).subset_convolve(SF(b)).as_list(),
                         brute_subset(a, b))


class TestEdgeCases(unittest.TestCase):
    def test_all_zero(self):
        z = [0, 0, 0, 0]
        for fn in ("or_convolve", "and_convolve", "xor_convolve",
                   "subset_convolve"):
            self.assertEqual(
                getattr(SetFunction(z), fn)(SF(z)).as_list(), [0, 0, 0, 0]
            )

    def test_all_one(self):
        o = [1, 1, 1, 1]
        self.assertEqual(SetFunction(o).or_convolve(SF(o)).as_list(),
                         [1, 3, 3, 9])
        self.assertEqual(SetFunction(o).subset_convolve(SF(o)).as_list(),
                         [1, 2, 2, 4])

    def test_negative_values(self):
        a = [-1, 2, -3, 4]
        b = [1, -2, 3, -4]
        self.assertEqual(SetFunction(a).xor_convolve(SF(b)).as_list(),
                         brute_xor(a, b))

    def test_pair_count(self):
        self.assertEqual(SetFunction([0] * 8).pair_count(), 64)

    def test_deterministic(self):
        a = SetFunction([1, 2, 3, 4])
        b = SF([5, 6, 7, 8])
        first = a.or_convolve(b).as_list()
        for _ in range(5):
            self.assertEqual(a.or_convolve(b).as_list(), first)


if __name__ == "__main__":
    unittest.main()
