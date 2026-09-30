"""暴力生成树计数的现有行为锁定测试。"""

import unittest

from mattree.count import (
    Erro,
    IllegalArgument,
    UnknownNode,
    check_graph,
    count_spanning_trees,
    degrees,
    enumerate_trees,
    is_connected,
    is_spanning_tree,
    normalize_edges,
)


class TestNormalizeEdges(unittest.TestCase):
    def test_keeps_order_and_duplicates(self):
        self.assertEqual(
            normalize_edges([(1, 0), (0, 1), (0, 1)]),
            [(1, 0), (0, 1), (0, 1)],
        )

    def test_accepts_lists_as_pairs(self):
        self.assertEqual(normalize_edges([[0, 2]]), [(0, 2)])

    def test_rejects_bare_string(self):
        with self.assertRaises(IllegalArgument):
            normalize_edges(["ab"])

    def test_rejects_wrong_arity(self):
        with self.assertRaises(IllegalArgument):
            normalize_edges([(0, 1, 2)])

    def test_rejects_bool_endpoint(self):
        with self.assertRaises(IllegalArgument):
            normalize_edges([(True, 0)])


class TestCheckGraph(unittest.TestCase):
    def test_positive_node_count_ok(self):
        self.assertEqual(check_graph(3, [(0, 1)]), [(0, 1)])

    def test_zero_nodes_rejected(self):
        with self.assertRaises(IllegalArgument):
            check_graph(0, [])

    def test_negative_nodes_rejected(self):
        with self.assertRaises(IllegalArgument):
            check_graph(-1, [])

    def test_bool_nodes_rejected(self):
        with self.assertRaises(IllegalArgument):
            check_graph(True, [])

    def test_endpoint_out_of_range(self):
        with self.assertRaises(UnknownNode):
            check_graph(2, [(0, 5)])


class TestConnectivity(unittest.TestCase):
    def test_single_node_is_connected(self):
        self.assertTrue(is_connected(1, []))

    def test_path_is_connected(self):
        self.assertTrue(is_connected(3, [(0, 1), (1, 2)]))

    def test_disconnected_split(self):
        self.assertFalse(is_connected(4, [(0, 1), (2, 3)]))

    def test_self_loop_does_not_connect(self):
        self.assertFalse(is_connected(2, [(0, 0)]))


class TestDegrees(unittest.TestCase):
    def test_empty_graph(self):
        self.assertEqual(degrees(3, []), [0, 0, 0])

    def test_path_degrees(self):
        self.assertEqual(degrees(3, [(0, 1), (1, 2)]), [1, 2, 1])

    def test_self_loop_counts_twice(self):
        self.assertEqual(degrees(2, [(0, 0)]), [2, 0])

    def test_parallel_edges_count_each(self):
        self.assertEqual(degrees(2, [(0, 1), (0, 1)]), [2, 2])


class TestIsSpanningTree(unittest.TestCase):
    def test_single_node_no_edges(self):
        self.assertTrue(is_spanning_tree(1, []))

    def test_wrong_edge_count(self):
        self.assertFalse(is_spanning_tree(3, [(0, 1)]))

    def test_cycle_is_not_tree(self):
        self.assertFalse(is_spanning_tree(3, [(0, 1), (1, 2), (2, 0)]))

    def test_path_is_tree(self):
        self.assertTrue(is_spanning_tree(3, [(0, 1), (1, 2)]))


class TestCountSpanningTrees(unittest.TestCase):
    def test_single_node(self):
        self.assertEqual(count_spanning_trees(1, []), 1)

    def test_two_nodes_one_edge(self):
        self.assertEqual(count_spanning_trees(2, [(0, 1)]), 1)

    def test_two_nodes_parallel_edges(self):
        self.assertEqual(count_spanning_trees(2, [(0, 1), (0, 1)]), 2)

    def test_triangle_has_three_trees(self):
        edges = [(0, 1), (1, 2), (2, 0)]
        self.assertEqual(count_spanning_trees(3, edges), 3)

    def test_complete_four_has_sixteen(self):
        edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        self.assertEqual(count_spanning_trees(4, edges), 16)

    def test_disconnected_is_zero(self):
        self.assertEqual(count_spanning_trees(3, [(0, 1)]), 0)

    def test_self_loop_ignored(self):
        edges = [(0, 1), (0, 0)]
        self.assertEqual(count_spanning_trees(2, edges), 1)

    def test_path_count_is_one(self):
        self.assertEqual(count_spanning_trees(4, [(0, 1), (1, 2), (2, 3)]), 1)


class TestEnumerateTrees(unittest.TestCase):
    def test_triangle_enumerates_three(self):
        edges = [(0, 1), (1, 2), (2, 0)]
        found = enumerate_trees(3, edges)
        self.assertEqual(len(found), 3)
        self.assertEqual(
            sorted(tuple(sorted(p)) for p in found),
            sorted([tuple(sorted(p)) for p in [
                [(0, 1), (1, 2)],
                [(0, 1), (2, 0)],
                [(1, 2), (2, 0)],
            ]]),
        )

    def test_disconnected_empty(self):
        self.assertEqual(enumerate_trees(3, [(0, 1)]), [])


class TestErrorHierarchy(unittest.TestCase):
    def test_illegal_argument_is_erro(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))

    def test_unknown_node_is_erro(self):
        self.assertTrue(issubclass(UnknownNode, Erro))

    def test_erro_is_exception(self):
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
