"""BruteMinCircle 现状行为的锁定测试（改造前基线，一个字都不许改）。

用一批固定点集，把当前那套枚举点对与三点再逐圆核验的做法所给出的事实逐
项钉死：空点集、单点、两点、三点共线、全部同点、四点共圆、等腰直角三角
形与钝角三角形的最小覆盖圆，圆心坐标与平方半径分别是多少；对非法参数是
不是当场抛出 Erro；圆之间的相等与可哈希又是怎样。这些数字都是基线实现实
际算出来的，任何一次改动只要动摇了既有对外行为，这里就会红。
"""

import unittest
from fractions import Fraction

from mincircle.circle import Erro, Circle, brute_min_circle


def assert_circle(test, got, cx, cy, r2):
    """逐项核对一个圆的圆心坐标与平方半径。"""
    test.assertEqual(got.cx, Fraction(cx))
    test.assertEqual(got.cy, Fraction(cy))
    test.assertEqual(got.r2, Fraction(r2))


class TestBasicShapes(unittest.TestCase):
    def test_empty(self):
        c = brute_min_circle([])
        assert_circle(self, c, 0, 0, 0)

    def test_single_point(self):
        c = brute_min_circle([(3, -4)])
        assert_circle(self, c, 3, -4, 0)

    def test_two_points(self):
        c = brute_min_circle([(0, 0), (10, 0)])
        assert_circle(self, c, 5, 0, 25)

    def test_two_points_tilted(self):
        c = brute_min_circle([(0, 0), (0, 6)])
        assert_circle(self, c, 0, 3, 9)

    def test_all_same_point(self):
        c = brute_min_circle([(7, 7), (7, 7), (7, 7), (7, 7)])
        assert_circle(self, c, 7, 7, 0)

    def test_duplicate_points_kept(self):
        c = brute_min_circle([(2, 2), (2, 2), (8, 2), (8, 2)])
        assert_circle(self, c, 5, 2, 9)


class TestCollinear(unittest.TestCase):
    def test_three_collinear_middle_diameter(self):
        c = brute_min_circle([(0, 0), (4, 0), (10, 0)])
        assert_circle(self, c, 5, 0, 25)

    def test_three_collinear_vertical(self):
        c = brute_min_circle([(0, -3), (0, 0), (0, 9)])
        assert_circle(self, c, 0, 3, 36)

    def test_three_collinear_between(self):
        c = brute_min_circle([(0, 0), (2, 0), (10, 0)])
        assert_circle(self, c, 5, 0, 25)


class TestCircumcircle(unittest.TestCase):
    def test_four_concyclic(self):
        c = brute_min_circle([(0, 0), (10, 0), (10, 10), (0, 10)])
        assert_circle(self, c, 5, 5, 50)

    def test_right_triangle(self):
        c = brute_min_circle([(0, 0), (10, 0), (0, 10)])
        assert_circle(self, c, 5, 5, 50)

    def test_obtuse_triangle_uses_longest_side(self):
        c = brute_min_circle([(0, 0), (10, 0), (1, 1)])
        assert_circle(self, c, 5, 0, 25)

    def test_non_integer_center(self):
        c = brute_min_circle([(0, 0), (3, 0), (0, 3)])
        assert_circle(self, c, Fraction(3, 2), Fraction(3, 2), Fraction(9, 2))


class TestCircleType(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(Circle(5, 5, 50), Circle(5, 5, 50))
        self.assertNotEqual(Circle(5, 5, 50), Circle(5, 5, 49))

    def test_hashable(self):
        seen = {Circle(1, 2, 3), Circle(1, 2, 3), Circle(1, 2, 4)}
        self.assertEqual(len(seen), 2)

    def test_contains(self):
        c = Circle(0, 0, 25)
        self.assertTrue(c.contains((5, 0)))
        self.assertTrue(c.contains((3, 4)))
        self.assertFalse(c.contains((6, 0)))
        self.assertFalse(c.contains((4, 4)))

    def test_repr(self):
        self.assertIn("Circle", repr(Circle(1, 2, 3)))


class TestErrors(unittest.TestCase):
    def test_non_sequence(self):
        with self.assertRaises(Erro):
            brute_min_circle(123)
        with self.assertRaises(Erro):
            brute_min_circle("abc")

    def test_bad_point_shape(self):
        with self.assertRaises(Erro):
            brute_min_circle([(0, 0, 0)])
        with self.assertRaises(Erro):
            brute_min_circle([(0,)])
        with self.assertRaises(Erro):
            brute_min_circle([0])

    def test_non_integer_coordinates(self):
        with self.assertRaises(Erro):
            brute_min_circle([(0.5, 0)])
        with self.assertRaises(Erro):
            brute_min_circle([(0, "1")])
        with self.assertRaises(Erro):
            brute_min_circle([(True, 0)])


if __name__ == "__main__":
    unittest.main()
