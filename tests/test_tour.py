"""TspSolver 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from tspx.tour import TspSolver, distance, tour_length


SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


class TestDistance(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(distance((0.0, 0.0), (3.0, 4.0)), 5.0)

    def test_same_point(self):
        self.assertEqual(distance((2.0, -1.0), (2.0, -1.0)), 0.0)


class TestTourLength(unittest.TestCase):
    def test_square_either_direction(self):
        self.assertEqual(tour_length(SQUARE, [0, 1, 2, 3]), 4.0)
        self.assertEqual(tour_length(SQUARE, [0, 3, 2, 1]), 4.0)

    def test_bowtie_is_longer(self):
        self.assertAlmostEqual(tour_length(SQUARE, [0, 2, 1, 3]), 2.0 + 2 ** 0.5 * 2)

    def test_single_point_is_zero(self):
        self.assertEqual(tour_length([(5.0, 5.0)], [0]), 0.0)

    def test_empty_is_zero(self):
        self.assertEqual(tour_length([], []), 0.0)


class TestEnumerateBest(unittest.TestCase):
    def test_two_points(self):
        pts = [(0.0, 0.0), (3.0, 4.0)]
        s = TspSolver(pts)
        length, order = s.enumerate_best()
        self.assertAlmostEqual(length, 10.0)
        self.assertEqual(sorted(order), [0, 1])

    def test_triangle(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (0.5, 3 ** 0.5 / 2)]
        s = TspSolver(pts)
        length, order = s.enumerate_best()
        self.assertAlmostEqual(length, 3.0)
        self.assertEqual(len(set(order)), 3)
        self.assertEqual(sorted(order), [0, 1, 2])

    def test_square_optimal(self):
        s = TspSolver(SQUARE)
        length, order = s.enumerate_best()
        self.assertAlmostEqual(length, 4.0)
        self.assertEqual(sorted(order), [0, 1, 2, 3])

    def test_duplicate_points_zero(self):
        s = TspSolver([(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)])
        length, order = s.enumerate_best()
        self.assertEqual(length, 0.0)
        self.assertEqual(len(order), 3)

    def test_single_point(self):
        s = TspSolver([(7.0, 8.0)])
        self.assertEqual(s.enumerate_best(), (0.0, [0]))

    def test_empty(self):
        s = TspSolver([])
        self.assertEqual(s.enumerate_best(), (0.0, []))

    def test_enumerate_count(self):
        self.assertEqual(TspSolver(SQUARE).enumerate_count(), 24)
        self.assertEqual(TspSolver([(0.0, 0.0)]).enumerate_count(), 0)
        self.assertEqual(TspSolver([]).enumerate_count(), 0)

    def test_deterministic_repeat(self):
        s = TspSolver(SQUARE)
        self.assertEqual(s.enumerate_best(), s.enumerate_best())


class TestNearestNeighbor(unittest.TestCase):
    def test_from_zero_on_square(self):
        s = TspSolver(SQUARE)
        order, length = s.nearest_neighbor(0)
        self.assertEqual(order[0], 0)
        self.assertEqual(sorted(order), [0, 1, 2, 3])
        self.assertAlmostEqual(length, 4.0)

    def test_over_starts_picks_min(self):
        s = TspSolver(SQUARE)
        length, order, start = s.nearest_neighbor_over_starts()
        self.assertAlmostEqual(length, 4.0)
        self.assertEqual(sorted(order), [0, 1, 2, 3])
        self.assertIn(start, [0, 1, 2, 3])

    def test_single_point_start_zero(self):
        s = TspSolver([(1.0, 2.0)])
        self.assertEqual(s.nearest_neighbor(0), ([0], 0.0))
        self.assertEqual(s.nearest_neighbor_over_starts(), (0.0, [0], 0))

    def test_empty(self):
        s = TspSolver([])
        self.assertEqual(s.nearest_neighbor(0), ([], 0.0))

    def test_points_stored_as_floats(self):
        s = TspSolver([(1, 2), (3, 4)])
        self.assertEqual(s.points, [(1.0, 2.0), (3.0, 4.0)])


if __name__ == "__main__":
    unittest.main()
