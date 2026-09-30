"""eulerx 朴素基线的锁定测试（改造前）。"""

import unittest

from eulerx import (
    EmptyEdgeError,
    EulerError,
    UnknownVertexError,
    chain_count,
    has_euler_circuit_undirected,
    has_euler_path_directed,
    has_euler_path_undirected,
    itoa,
    make_directed,
    make_undirected,
    naive_edge_order_check_count,
    naive_euler_circuit_undirected,
    naive_euler_path_directed,
    naive_euler_path_undirected,
)


def undirected(edges, vertices=()):
    g = make_undirected()
    for v in vertices:
        g.add_vertex(v)
    for u, v in edges:
        g.add_edge(u, v)
    return g


def directed(arcs, vertices=()):
    g = make_directed()
    for v in vertices:
        g.add_vertex(v)
    for u, v in arcs:
        g.add_arc(u, v)
    return g


class TestBuild(unittest.TestCase):
    def test_vertices_sorted(self):
        g = undirected([(2, 0)], vertices=[9])
        self.assertEqual(g.vertices(), [0, 2, 9])

    def test_undirected_edges_normalized(self):
        g = undirected([(2, 1), (0, 3)])
        self.assertEqual(g.undirected_edges(), [(0, 3), (1, 2)])

    def test_parallel_edges_kept(self):
        g = undirected([(0, 1), (0, 1)])
        self.assertEqual(g.undirected_edges(), [(0, 1), (0, 1)])

    def test_directed_edges_sorted(self):
        g = directed([(1, 0), (0, 2)])
        self.assertEqual(g.directed_edges(), [(0, 2), (1, 0)])

    def test_is_directed(self):
        self.assertFalse(make_undirected().is_directed())
        self.assertTrue(make_directed().is_directed())


class TestDegree(unittest.TestCase):
    def test_degree_counts_self_loop_twice(self):
        g = undirected([(0, 0), (0, 1)])
        self.assertEqual(g.degree(), {0: 3, 1: 1})

    def test_degree_of_vertex(self):
        g = undirected([(0, 1), (0, 2)])
        self.assertEqual(g.degree(0), 2)

    def test_odd_degree_vertices(self):
        g = undirected([(0, 1), (1, 2), (2, 3)])
        self.assertEqual(g.odd_degree_vertices(), [0, 3])

    def test_in_out_degree(self):
        g = directed([(0, 1), (0, 2), (1, 2)])
        indeg, outdeg = g.in_out_degree()
        self.assertEqual(outdeg[0], 2)
        self.assertEqual(indeg[2], 2)

    def test_degree_on_directed_raises(self):
        with self.assertRaises(EulerError):
            directed([(0, 1)]).degree()

    def test_degree_of_unknown_raises(self):
        with self.assertRaises(UnknownVertexError):
            undirected([(0, 1)]).degree(9)


class TestEdgeKindGuard(unittest.TestCase):
    def test_add_edge_on_directed_raises(self):
        with self.assertRaises(EulerError):
            make_directed().add_edge(0, 1)

    def test_add_arc_on_undirected_raises(self):
        with self.assertRaises(EulerError):
            make_undirected().add_arc(0, 1)


class TestFeasibility(unittest.TestCase):
    def test_triangle_has_path_and_circuit(self):
        g = undirected([(0, 1), (1, 2), (0, 2)])
        self.assertTrue(has_euler_path_undirected(g))
        self.assertTrue(has_euler_circuit_undirected(g))

    def test_two_odd_points_has_path(self):
        g = undirected([(0, 1), (1, 2)])
        self.assertTrue(has_euler_path_undirected(g))
        self.assertFalse(has_euler_circuit_undirected(g))

    def test_four_odd_points_no_path(self):
        g = undirected([(0, 1), (0, 2), (0, 3)])
        self.assertFalse(has_euler_path_undirected(g))

    def test_disconnected_over_edges(self):
        g = undirected([(0, 1), (2, 3)])
        self.assertFalse(has_euler_path_undirected(g))

    def test_empty_graph_raises(self):
        with self.assertRaises(EmptyEdgeError):
            has_euler_path_undirected(undirected([], vertices=[0]))
        with self.assertRaises(EmptyEdgeError):
            has_euler_circuit_undirected(undirected([], vertices=[0]))

    def test_isolated_vertices_ignored(self):
        g = undirected([(0, 1), (1, 2)], vertices=[9])
        self.assertTrue(has_euler_path_undirected(g))


class TestNaiveUndirected(unittest.TestCase):
    def test_triangle(self):
        g = undirected([(0, 1), (1, 2), (0, 2)])
        self.assertEqual(naive_euler_path_undirected(g), [0, 1, 2, 0])
        self.assertEqual(naive_euler_circuit_undirected(g), [0, 1, 2, 0])

    def test_single_edge(self):
        g = undirected([(0, 1)])
        self.assertEqual(naive_euler_path_undirected(g), [0, 1])
        self.assertIsNone(naive_euler_circuit_undirected(g))

    def test_chain_picks_lex_smallest(self):
        g = undirected([(0, 1), (1, 2)])
        self.assertEqual(naive_euler_path_undirected(g), [0, 1, 2])

    def test_start_constraint(self):
        g = undirected([(0, 1), (1, 2)])
        self.assertEqual(naive_euler_path_undirected(g, start=2), [2, 1, 0])

    def test_self_loop(self):
        g = undirected([(0, 0), (0, 1)])
        self.assertEqual(naive_euler_path_undirected(g), [0, 0, 1])

    def test_parallel_edges(self):
        g = undirected([(0, 1), (0, 1)])
        self.assertTrue(has_euler_circuit_undirected(g))
        self.assertEqual(naive_euler_circuit_undirected(g), [0, 1, 0])

    def test_no_path_returns_none(self):
        g = undirected([(0, 1), (0, 2), (0, 3)])
        self.assertIsNone(naive_euler_path_undirected(g))

    def test_no_edges_returns_none(self):
        g = undirected([], vertices=[0])
        self.assertIsNone(naive_euler_path_undirected(g))


class TestNaiveDirected(unittest.TestCase):
    def test_directed_chain(self):
        g = directed([(0, 1), (1, 2)])
        self.assertTrue(has_euler_path_directed(g))
        self.assertEqual(naive_euler_path_directed(g), [0, 1, 2])

    def test_unbalanced_has_no_path(self):
        g = directed([(0, 1), (0, 2)])
        self.assertFalse(has_euler_path_directed(g))
        self.assertIsNone(naive_euler_path_directed(g))


class TestScale(unittest.TestCase):
    def test_check_count_is_factorial(self):
        g = undirected([(0, 1), (1, 2), (2, 3)])
        self.assertEqual(naive_edge_order_check_count(g), 6)

    def test_check_count_five_edges(self):
        g = undirected([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])
        self.assertEqual(naive_edge_order_check_count(g), 120)


class TestChaining(unittest.TestCase):
    def test_two_chainable(self):
        self.assertEqual(chain_count(["ab", "bc"]), 1)

    def test_both_orders(self):
        self.assertEqual(chain_count(["ab", "ba"]), 2)

    def test_not_chainable(self):
        self.assertEqual(chain_count(["ab", "cd"]), 0)


class TestNaming(unittest.TestCase):
    def test_itoa(self):
        self.assertEqual(itoa(0), "A")
        self.assertEqual(itoa(25), "Z")
        self.assertEqual(itoa(26), "AA")


if __name__ == "__main__":
    unittest.main()
