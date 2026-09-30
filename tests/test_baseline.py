"""Tree 与路径统计现有行为的锁定测试（基线，一字不改）。"""

import unittest

from centdecomp import (
    CentdecompError,
    QueryError,
    Tree,
    TreeError,
    count_at_most,
    count_exact,
    diameter,
    enumerate_pair_visits,
)
from centdecomp.shapes import balanced, chain, star


class TestShapes(unittest.TestCase):
    def test_chain_shape(self):
        t = chain(4)
        self.assertEqual(t.n, 4)
        self.assertEqual(t.degree(0), 1)
        self.assertEqual(t.degree(1), 2)

    def test_star_shape(self):
        t = star(3)
        self.assertEqual(t.degree(0), 3)

    def test_balanced_shape_is_deterministic(self):
        t = balanced(7)
        self.assertEqual(t.neighbors(0), [(1, 1), (2, 1)])
        self.assertEqual(t.degree(3), 1)

    def test_single_is_one_vertex(self):
        self.assertEqual(Tree(1).n, 1)


class TestTreeConstruction(unittest.TestCase):
    def test_n_must_be_positive(self):
        with self.assertRaises(TreeError):
            Tree(0)

    def test_n_must_be_int(self):
        with self.assertRaises(TreeError):
            Tree(2.5)

    def test_edge_out_of_range(self):
        t = Tree(3)
        with self.assertRaises(TreeError):
            t.add_edge(0, 3)

    def test_negative_weight_rejected(self):
        t = Tree(2)
        with self.assertRaises(TreeError):
            t.add_edge(0, 1, -1)

    def test_degrees_and_neighbors(self):
        t = star(3)
        self.assertEqual(t.degree(0), 3)
        self.assertEqual(t.neighbors(1), [(0, 1)])
        self.assertEqual(len(t.edges()), 3)

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(TreeError, CentdecompError))
        self.assertTrue(issubclass(QueryError, CentdecompError))


class TestPathDistance(unittest.TestCase):
    def test_same_vertex_is_zero(self):
        t = chain(4)
        self.assertEqual(t.path_distance(2, 2), 0)

    def test_chain_distances(self):
        t = chain(4)
        self.assertEqual(t.path_distance(0, 3), 3)
        self.assertEqual(t.path_distance(1, 3), 2)

    def test_all_pairs_are_sorted(self):
        t = chain(4)
        pairs = t.all_pairs_distances()
        self.assertEqual(len(pairs), 6)
        self.assertEqual(pairs[0], (0, 1, 1))
        self.assertEqual(pairs[-1], (2, 3, 1))

    def test_wrong_vertex_id_rejected(self):
        t = chain(3)
        with self.assertRaises(TreeError):
            t.path_distance(0, 5)


class TestCounts(unittest.TestCase):
    def test_chain_exact(self):
        t = chain(4)
        self.assertEqual(count_exact(t, 1), 3)
        self.assertEqual(count_exact(t, 2), 2)
        self.assertEqual(count_exact(t, 3), 1)

    def test_chain_at_most(self):
        t = chain(4)
        self.assertEqual(count_at_most(t, 1), 3)
        self.assertEqual(count_at_most(t, 2), 5)
        self.assertEqual(count_at_most(t, 100), 6)

    def test_star_exact_and_at_most(self):
        t = star(3)
        self.assertEqual(count_exact(t, 2), 3)
        self.assertEqual(count_at_most(t, 1), 3)

    def test_zero_weight_edge(self):
        t = Tree(3)
        t.add_edge(0, 1, 0)
        t.add_edge(1, 2, 1)
        self.assertEqual(count_exact(t, 0), 1)
        self.assertEqual(count_exact(t, 1), 2)

    def test_single_node_has_no_pairs(self):
        t = Tree(1)
        self.assertEqual(count_exact(t, 0), 0)
        self.assertEqual(count_at_most(t, 5), 0)
        self.assertEqual(t.pair_count(), 0)

    def test_bad_query_rejected(self):
        t = chain(3)
        with self.assertRaises(QueryError):
            count_exact(t, -1)
        with self.assertRaises(QueryError):
            count_at_most(t, -1)


class TestDiameter(unittest.TestCase):
    def test_chain_diameter(self):
        self.assertEqual(diameter(chain(4)), (3, 0, 3))

    def test_single_node(self):
        self.assertEqual(diameter(Tree(1)), (0, 0, 0))

    def test_two_nodes(self):
        self.assertEqual(diameter(chain(2)), (1, 0, 1))

    def test_star_tie_breaks_lexicographically(self):
        self.assertEqual(diameter(star(3)), (2, 1, 2))


class TestNaiveVisits(unittest.TestCase):
    def test_visits_equal_pair_count(self):
        t = chain(5)
        self.assertEqual(enumerate_pair_visits(t), 10)
        self.assertEqual(enumerate_pair_visits(t), t.pair_count())


if __name__ == "__main__":
    unittest.main()
