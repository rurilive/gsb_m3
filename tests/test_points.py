"""LinearPoints 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：插入、删除、包含判断与矩形查询的确定性。
新增行为（四叉树、圆形与最近邻、动态增删、分裂合并）另建测试文件，
不改动本文件。
"""

import unittest

from quadrex import LinearPoints
from quadrex.points import QuadError


POINTS = [(0, 0), (1, 1), (2, 2), (3, 3), (-1, -1), (2, 0), (0, 2)]


class TestInsertAndMembership(unittest.TestCase):
    def test_empty_set(self):
        s = LinearPoints()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.points(), [])
        self.assertEqual(s.query_rect(-1, -1, 1, 1), [])

    def test_insert_returns_true_then_false(self):
        s = LinearPoints()
        self.assertTrue(s.insert(1, 2))
        self.assertFalse(s.insert(1, 2))
        self.assertEqual(len(s), 1)

    def test_contains(self):
        s = LinearPoints(POINTS)
        self.assertTrue(s.contains(1, 1))
        self.assertFalse(s.contains(9, 9))
        self.assertIn((2, 0), s)

    def test_points_sorted(self):
        s = LinearPoints([(3, 3), (0, 0), (1, 1)])
        self.assertEqual(s.points(), [(0, 0), (1, 1), (3, 3)])


class TestRemove(unittest.TestCase):
    def test_remove_existing(self):
        s = LinearPoints(POINTS)
        self.assertTrue(s.remove(1, 1))
        self.assertFalse(s.contains(1, 1))
        self.assertEqual(len(s), len(POINTS) - 1)

    def test_remove_missing(self):
        s = LinearPoints(POINTS)
        self.assertFalse(s.remove(5, 5))
        self.assertEqual(len(s), len(POINTS))


class TestQueryRect(unittest.TestCase):
    def test_hits_are_sorted(self):
        s = LinearPoints(POINTS)
        self.assertEqual(s.query_rect(0, 0, 2, 2), [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)])

    def test_boundary_inclusive(self):
        s = LinearPoints([(0, 0), (1, 0), (2, 0)])
        self.assertEqual(s.query_rect(1, 0, 1, 0), [(1, 0)])
        self.assertEqual(s.query_rect(0, 0, 2, 0), [(0, 0), (1, 0), (2, 0)])

    def test_empty_rect_by_position(self):
        s = LinearPoints(POINTS)
        self.assertEqual(s.query_rect(10, 10, 20, 20), [])

    def test_degenerate_rect_single_point(self):
        s = LinearPoints(POINTS)
        self.assertEqual(s.query_rect(2, 2, 2, 2), [(2, 2)])

    def test_covering_rect_returns_all(self):
        s = LinearPoints(POINTS)
        self.assertEqual(s.query_rect(-100, -100, 100, 100), s.points())


class TestGuards(unittest.TestCase):
    def test_bad_coordinate_rejected(self):
        s = LinearPoints()
        with self.assertRaises(QuadError):
            s.insert("x", 1)
        with self.assertRaises(QuadError):
            s.insert(float("inf"), 0)
        with self.assertRaises(QuadError):
            s.insert(float("nan"), 0)

    def test_bad_rect_rejected(self):
        s = LinearPoints(POINTS)
        with self.assertRaises(QuadError):
            s.query_rect(1, 0, 0, 1)
        with self.assertRaises(QuadError):
            s.query_rect(0, 0, 1, "y")

    def test_quad_error_is_base(self):
        self.assertTrue(issubclass(QuadError, Exception))


if __name__ == "__main__":
    unittest.main()
