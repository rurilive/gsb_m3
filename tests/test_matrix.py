"""DenseMatrix 现有行为的锁定测试。"""

import unittest

from sparsem.matrix import DenseMatrix


def make(rows, cols, value=0):
    return [[value for _ in range(cols)] for _ in range(rows)]


class TestConstruction(unittest.TestCase):
    def test_shape(self):
        m = DenseMatrix(2, 3, [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(m.rows(), 2)
        self.assertEqual(m.cols(), 3)

    def test_negative_shape_rejected(self):
        with self.assertRaises(ValueError):
            DenseMatrix(-1, 2, [])

    def test_non_int_shape_rejected(self):
        with self.assertRaises(TypeError):
            DenseMatrix(2.0, 2, [])


class TestAccess(unittest.TestCase):
    def test_get_and_set(self):
        m = DenseMatrix(2, 2, [[1, 0], [0, 2]])
        self.assertEqual(m.get(0, 0), 1)
        self.assertEqual(m.get(0, 1), 0)
        m.set(0, 1, 9)
        self.assertEqual(m.get(0, 1), 9)

    def test_set_returns_self(self):
        m = DenseMatrix(1, 1, [[0]])
        self.assertIs(m.set(0, 0, 5), m)

    def test_get_out_of_range(self):
        m = DenseMatrix(1, 1, [[0]])
        with self.assertRaises(IndexError):
            m.get(1, 0)
        with self.assertRaises(IndexError):
            m.get(0, -1)


class TestConversionAndEquality(unittest.TestCase):
    def test_to_dense_roundtrip(self):
        grid = [[1, 0], [0, 2]]
        m = DenseMatrix(2, 2, grid)
        self.assertEqual(m.to_dense(), grid)

    def test_to_dense_is_copy(self):
        m = DenseMatrix(1, 1, [[1]])
        out = m.to_dense()
        out[0][0] = 99
        self.assertEqual(m.get(0, 0), 1)

    def test_equals(self):
        a = DenseMatrix(2, 2, [[1, 0], [0, 2]])
        b = DenseMatrix(2, 2, [[1, 0], [0, 2]])
        c = DenseMatrix(2, 2, [[1, 0], [0, 3]])
        self.assertTrue(a.equals(b))
        self.assertFalse(a.equals(c))

    def test_equals_shape_mismatch(self):
        a = DenseMatrix(1, 2, [[1, 2]])
        b = DenseMatrix(2, 1, [[1], [2]])
        self.assertFalse(a.equals(b))

    def test_zeros_are_stored(self):
        m = DenseMatrix(2, 3, make(2, 3, 0))
        self.assertEqual(m.to_dense(), [[0, 0, 0], [0, 0, 0]])


if __name__ == "__main__":
    unittest.main()
