"""boruvka 改造前现状的锁定测试。

这些用例锁住朴素实现的行为：最小生成森林所选边的下标、权值、连通性、
分量划分，以及规模之外的全部边界。测试一个字不改，改造后必须仍然全绿。
"""

import unittest

from boruvka.mst import (
    Erro,
    IllegalArgument,
    UnknownNode,
    check_graph,
    components,
    is_connected,
    mst_edges,
    mst_weight,
    normalize_edges,
)


class TestChecks(unittest.TestCase):
    def test_node_count_must_be_int(self):
        for bad in (True, 1.5, "2", None):
            with self.assertRaises(IllegalArgument):
                check_graph(bad, [])

    def test_node_count_must_be_positive(self):
        for bad in (0, -1, -5):
            with self.assertRaises(IllegalArgument):
                check_graph(bad, [])

    def test_edges_must_be_sequence(self):
        with self.assertRaises(IllegalArgument):
            check_graph(3, 5)

    def test_each_edge_is_a_triple(self):
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(0, 1)])
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(0, 1, 2, 3)])

    def test_endpoint_must_be_int(self):
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(True, 1, 2)])

    def test_endpoint_range(self):
        with self.assertRaises(UnknownNode):
            check_graph(3, [(0, 3, 1)])
        with self.assertRaises(UnknownNode):
            check_graph(3, [(-1, 1, 1)])

    def test_weight_must_be_non_negative_int(self):
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(0, 1, -1)])
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(0, 1, 2.5)])
        with self.assertRaises(IllegalArgument):
            check_graph(3, [(0, 1, True)])


class TestNormalize(unittest.TestCase):
    def test_keeps_order_and_builds_triples(self):
        es = normalize_edges(3, [[0, 1, 2], (1, 2, 3)])
        self.assertEqual(es, [(0, 1, 2), (1, 2, 3)])

    def test_keeps_self_loops_and_parallel(self):
        es = normalize_edges(2, [(0, 0, 1), (0, 1, 5), (0, 1, 5)])
        self.assertEqual(es, [(0, 0, 1), (0, 1, 5), (0, 1, 5)])


class TestConnectivity(unittest.TestCase):
    def test_single_node_is_connected(self):
        self.assertTrue(is_connected(1, []))

    def test_chain_is_connected(self):
        self.assertTrue(is_connected(3, [(0, 1, 1), (1, 2, 1)]))

    def test_split_is_disconnected(self):
        self.assertFalse(is_connected(4, [(0, 1, 1), (2, 3, 1)]))

    def test_empty_edges_on_several_nodes(self):
        self.assertFalse(is_connected(3, []))


class TestComponents(unittest.TestCase):
    def test_partition(self):
        got = components(4, [(0, 1, 1), (2, 3, 1)])
        self.assertEqual(got, [[0, 1], [2, 3]])

    def test_isolated_nodes_are_singletons(self):
        got = components(3, [(0, 1, 1)])
        self.assertEqual(got, [[0, 1], [2]])

    def test_self_loop_does_not_merge(self):
        got = components(2, [(0, 0, 1)])
        self.assertEqual(got, [[0], [1]])


class TestMst(unittest.TestCase):
    def test_single_node_has_no_edge(self):
        self.assertEqual(mst_edges(1, []), [])
        self.assertEqual(mst_weight(1, []), 0)

    def test_two_nodes_one_edge(self):
        self.assertEqual(mst_edges(2, [(0, 1, 5)]), [0])
        self.assertEqual(mst_weight(2, [(0, 1, 5)]), 5)

    def test_triangle_picks_two_lightest(self):
        edges = [(0, 1, 1), (1, 2, 2), (0, 2, 3)]
        self.assertEqual(mst_edges(3, edges), [0, 1])
        self.assertEqual(mst_weight(3, edges), 3)

    def test_parallel_edges_tie_pick_lowest_index(self):
        edges = [(0, 1, 4), (0, 1, 4)]
        self.assertEqual(mst_edges(2, edges), [0])

    def test_parallel_edges_cheapest_wins(self):
        edges = [(0, 1, 5), (0, 1, 5), (0, 1, 1)]
        self.assertEqual(mst_edges(2, edges), [2])
        self.assertEqual(mst_weight(2, edges), 1)

    def test_self_loop_is_ignored(self):
        edges = [(0, 0, 0), (0, 1, 7)]
        self.assertEqual(mst_edges(2, edges), [1])
        self.assertEqual(mst_weight(2, edges), 7)

    def test_disconnected_gives_forest(self):
        edges = [(0, 1, 2), (2, 3, 3)]
        self.assertEqual(mst_edges(4, edges), [0, 1])
        self.assertEqual(mst_weight(4, edges), 5)

    def test_isolated_node_is_ignored(self):
        self.assertEqual(mst_edges(4, [(0, 1, 2)]), [0])

    def test_empty_edges_on_several_nodes(self):
        self.assertEqual(mst_edges(3, []), [])
        self.assertEqual(mst_weight(3, []), 0)

    def test_result_is_deterministic(self):
        edges = [(0, 1, 3), (1, 2, 1), (2, 3, 3), (0, 3, 2), (1, 3, 1)]
        first = mst_edges(4, edges)
        second = mst_edges(4, edges)
        self.assertEqual(first, second)

    def test_selected_indices_ascending_by_weight(self):
        edges = [(0, 1, 9), (1, 2, 1), (2, 3, 5)]
        got = mst_edges(4, edges)
        weights = [edges[i][2] for i in got]
        self.assertEqual(weights, sorted(weights))


class TestErrorBase(unittest.TestCase):
    def test_all_errors_share_base(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))
        self.assertTrue(issubclass(UnknownNode, Erro))

    def test_catch_by_base(self):
        with self.assertRaises(Erro):
            check_graph(3, [(0, 9, 1)])


if __name__ == "__main__":
    unittest.main()
