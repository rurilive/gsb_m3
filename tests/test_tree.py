"""PointSet 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与维度校验、最近邻、k 近邻排序、
矩形与球范围查询、最近点对、半径计数、平局口径与异常层级。
改造时本文件一个字都不许改，新行为一律另开测试文件。
"""

import unittest

from kdx.tree import (
    DimensionMismatchError,
    EmptyPointSetError,
    InvalidKError,
    InvalidPointsError,
    InvalidRadiusError,
    KdxError,
    PointSet,
    nearest_pair,
    radius_count,
)


def grid():
    return PointSet([
        (0.0, 0.0),
        (1.0, 0.0),
        (0.0, 1.0),
        (2.0, 2.0),
        (3.0, 1.0),
    ])


class TestConstruction(unittest.TestCase):
    def test_dimension(self):
        ps = PointSet([(0, 0, 0), (1, 2, 3)])
        self.assertEqual(ps.dimension, 3)

    def test_size(self):
        self.assertEqual(grid().size(), 5)
        self.assertEqual(len(grid()), 5)

    def test_empty_allowed(self):
        ps = PointSet([])
        self.assertEqual(ps.size(), 0)
        self.assertEqual(ps.dimension, 0)

    def test_points_returns_copy(self):
        ps = grid()
        got = ps.points
        got.append((9, 9))
        self.assertEqual(ps.size(), 5)

    def test_ragged_dimension_raises(self):
        with self.assertRaises(InvalidPointsError):
            PointSet([(0, 0), (1, 2, 3)])

    def test_non_number_coord_raises(self):
        with self.assertRaises(InvalidPointsError):
            PointSet([(0, "x")])

    def test_bool_coord_raises(self):
        with self.assertRaises(InvalidPointsError):
            PointSet([(0, True)])

    def test_empty_point_raises(self):
        with self.assertRaises(InvalidPointsError):
            PointSet([()])


class TestNearest(unittest.TestCase):
    def test_basic(self):
        idx, dist = grid().nearest((0.1, 0.1))
        self.assertEqual(idx, 0)
        self.assertAlmostEqual(dist, (0.1 ** 2 + 0.1 ** 2) ** 0.5)

    def test_query_is_member(self):
        idx, dist = grid().nearest((2.0, 2.0))
        self.assertEqual(idx, 3)
        self.assertAlmostEqual(dist, 0.0)

    def test_tie_prefers_smaller_index(self):
        ps = PointSet([(1.0, 0.0), (0.0, 1.0)])
        idx, dist = ps.nearest((0.0, 0.0))
        self.assertEqual(idx, 0)
        self.assertAlmostEqual(dist, 1.0)

    def test_empty_raises(self):
        with self.assertRaises(EmptyPointSetError):
            PointSet([]).nearest((0, 0))

    def test_dimension_mismatch_raises(self):
        with self.assertRaises(DimensionMismatchError):
            grid().nearest((0, 0, 0))


class TestKNearest(unittest.TestCase):
    def test_order_within(self):
        got = grid().knearest((0.0, 0.0), 3)
        self.assertEqual([i for i, _ in got], [0, 1, 2])

    def test_limit_by_size(self):
        got = grid().knearest((0.0, 0.0), 999)
        self.assertEqual(len(got), 5)

    def test_first_is_nearest(self):
        got = grid().knearest((2.9, 1.1), 1)
        self.assertEqual(got[0][0], 4)

    def test_tie_break_by_index(self):
        ps = PointSet([(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)])
        got = ps.knearest((0.0, 0.0), 2)
        self.assertEqual([i for i, _ in got], [0, 1])

    def test_invalid_k_raises(self):
        for bad in (0, -1, 1.5, "2", True):
            with self.assertRaises(InvalidKError):
                grid().knearest((0, 0), bad)


class TestRangeRect(unittest.TestCase):
    def test_basic(self):
        got = grid().range_query_rect((0.0, 0.0), (1.0, 1.0))
        self.assertEqual(got, [0, 1, 2])

    def test_boundary_inclusive(self):
        got = grid().range_query_rect((2.0, 2.0), (3.0, 2.0))
        self.assertEqual(got, [3])

    def test_empty_result(self):
        self.assertEqual(grid().range_query_rect((10, 10), (11, 11)), [])

    def test_inverted_bounds_raise(self):
        with self.assertRaises(InvalidPointsError):
            grid().range_query_rect((1.0, 0.0), (0.0, 1.0))

    def test_dimension_mismatch_raises(self):
        with self.assertRaises(DimensionMismatchError):
            grid().range_query_rect((0, 0, 0), (1, 1, 1))


class TestRangeBall(unittest.TestCase):
    def test_basic(self):
        got = grid().range_query_ball((0.0, 0.0), 1.0)
        self.assertEqual(got, [0, 1, 2])

    def test_radius_zero(self):
        got = grid().range_query_ball((3.0, 1.0), 0.0)
        self.assertEqual(got, [4])

    def test_large_radius(self):
        got = grid().range_query_ball((0.0, 0.0), 100.0)
        self.assertEqual(got, [0, 1, 2, 3, 4])

    def test_negative_radius_raises(self):
        with self.assertRaises(InvalidRadiusError):
            grid().range_query_ball((0, 0), -1.0)


class TestNearestPair(unittest.TestCase):
    def test_basic(self):
        ps = PointSet([(0.0, 0.0), (10.0, 0.0), (1.0, 0.0)])
        i, j, dist = ps.nearest_pair()
        self.assertEqual((i, j), (0, 2))
        self.assertAlmostEqual(dist, 1.0)

    def test_fewer_than_two_raises(self):
        with self.assertRaises(EmptyPointSetError):
            PointSet([(0.0, 0.0)]).nearest_pair()

    def test_tie_prefers_lexicographic_pair(self):
        ps = PointSet([(0.0, 0.0), (1.0, 0.0), (5.0, 0.0), (6.0, 0.0)])
        i, j, dist = ps.nearest_pair()
        self.assertEqual((i, j), (0, 1))
        self.assertAlmostEqual(dist, 1.0)


class TestRadiusCount(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(grid().radius_count((0.0, 0.0), 1.0), 3)

    def test_zero_radius_member(self):
        self.assertEqual(grid().radius_count((2.0, 2.0), 0.0), 1)

    def test_none_inside(self):
        self.assertEqual(grid().radius_count((100.0, 100.0), 0.5), 0)


class TestModuleHelpers(unittest.TestCase):
    def test_nearest_pair_helper(self):
        i, j, dist = nearest_pair([(0.0, 0.0), (3.0, 4.0)])
        self.assertEqual((i, j), (0, 1))
        self.assertAlmostEqual(dist, 5.0)

    def test_radius_count_helper(self):
        self.assertEqual(radius_count([(0.0, 0.0), (5.0, 0.0)], (0.0, 0.0), 1.0), 1)


class TestPruningCountBaseline(unittest.TestCase):
    def test_pruning_is_zero(self):
        ps = grid()
        ps.nearest((0.3, 0.4))
        ps.knearest((0.3, 0.4), 2)
        ps.range_query_rect((0, 0), (2, 2))
        self.assertEqual(ps.pruning_count, 0)


class TestDeterminism(unittest.TestCase):
    def test_nearest_repeatable(self):
        ps = grid()
        self.assertEqual(ps.nearest((0.4, 0.2)), ps.nearest((0.4, 0.2)))

    def test_knearest_repeatable(self):
        ps = grid()
        self.assertEqual(ps.knearest((0.4, 0.2), 3), ps.knearest((0.4, 0.2), 3))

    def test_no_shared_state_between_instances(self):
        a = grid()
        b = PointSet([(0.0, 0.0)])
        self.assertEqual(a.size(), 5)
        self.assertEqual(b.size(), 1)


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (InvalidPointsError, DimensionMismatchError,
                    EmptyPointSetError, InvalidKError, InvalidRadiusError):
            self.assertTrue(issubclass(exc, KdxError))

    def test_catchable_via_base(self):
        with self.assertRaises(KdxError):
            PointSet([(0, 0)]).nearest((0, 0, 0))


if __name__ == "__main__":
    unittest.main()
