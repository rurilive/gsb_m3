"""stoerwagner 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from stoerwagner.naive import (
    CutError,
    Erro,
    GraphError,
    MinCutTools,
    exhaustive_min_cut_value,
    max_flow_value,
    normalize_edges,
    pairwise_min_cut_value,
)


# 三点点链：全局最小割是两条里最小的那条，权重为一。
PATH_GRAPH = [
    (0, 1, 1, 0),
    (1, 2, 2, 1),
]

# 四点点团，每条边权重为一，任意单点与其余三点的割权都是三。
CLIQUE4 = [
    (0, 1, 1, 0),
    (1, 2, 1, 1),
    (2, 3, 1, 2),
    (0, 3, 1, 3),
    (0, 2, 1, 4),
    (1, 3, 1, 5),
]

# 一对点之间两条平行边，权重累加后这个点对的割权是四。
PARALLEL_GRAPH = [
    (0, 1, 2, 0),
    (0, 1, 3, 1),
    (1, 2, 4, 2),
]

# 星形：中心连三条不同权重的边，最小割就是最细的那根辐条。
STAR_GRAPH = [
    (0, 1, 5, 0),
    (0, 2, 6, 1),
    (0, 3, 7, 2),
]


class TestPairwiseMinCut(unittest.TestCase):
    def test_path_graph(self):
        self.assertEqual(pairwise_min_cut_value(PATH_GRAPH), 1)

    def test_clique(self):
        self.assertEqual(pairwise_min_cut_value(CLIQUE4), 3)

    def test_parallel_edges_add_up(self):
        self.assertEqual(pairwise_min_cut_value(PARALLEL_GRAPH), 4)

    def test_two_node_graph(self):
        self.assertEqual(pairwise_min_cut_value([(0, 1, 9, 0)]), 9)

    def test_star_graph(self):
        self.assertEqual(pairwise_min_cut_value(STAR_GRAPH), 5)

    def test_zero_weight_graph(self):
        edges = [(0, 1, 0, 0), (1, 2, 5, 1), (0, 2, 5, 2), (2, 3, 0, 3)]
        self.assertEqual(pairwise_min_cut_value(edges), 0)

    def test_single_node_rejected(self):
        with self.assertRaises(CutError):
            pairwise_min_cut_value([])

    def test_counter_accumulates(self):
        counter = [0]
        pairwise_min_cut_value(CLIQUE4, counter)
        self.assertGreater(counter[0], 0)

    def test_repeated_run_same_result(self):
        first = pairwise_min_cut_value(CLIQUE4)
        for _ in range(3):
            self.assertEqual(pairwise_min_cut_value(CLIQUE4), first)


class TestExhaustive(unittest.TestCase):
    def test_matches_value_on_path(self):
        self.assertEqual(exhaustive_min_cut_value(PATH_GRAPH), 1)

    def test_matches_value_on_clique(self):
        self.assertEqual(exhaustive_min_cut_value(CLIQUE4), 3)

    def test_agree_with_pairwise(self):
        for graph in (PATH_GRAPH, CLIQUE4, PARALLEL_GRAPH, STAR_GRAPH):
            self.assertEqual(
                exhaustive_min_cut_value(graph),
                pairwise_min_cut_value(graph))

    def test_needs_two_nodes(self):
        with self.assertRaises(CutError):
            exhaustive_min_cut_value([])


class TestMaxFlow(unittest.TestCase):
    def test_path_source_to_sink(self):
        self.assertEqual(max_flow_value(PATH_GRAPH, 0, 2), 1)

    def test_source_equals_sink_rejected(self):
        with self.assertRaises(CutError):
            max_flow_value(PATH_GRAPH, 0, 0)

    def test_unknown_node_gives_zero(self):
        self.assertEqual(max_flow_value(PATH_GRAPH, 0, 99), 0)


class TestEdgeTable(unittest.TestCase):
    def test_three_tuple_gets_index_id(self):
        arcs, nodes = normalize_edges([(0, 1, 5), (1, 2, 6)])
        self.assertEqual([arc[3] for arc in arcs], [0, 1])
        self.assertEqual(sorted(nodes), [0, 1, 2])

    def test_two_tuple_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 1)])

    def test_five_tuple_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 1, 1, 2, 3)])

    def test_duplicate_id_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 1, 1, 0), (1, 2, 1, 0)])

    def test_self_loop_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 0, 1, 0)])

    def test_negative_weight_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 1, -1, 0)])

    def test_bool_weight_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges([(0, 1, True, 0)])

    def test_none_rejected(self):
        with self.assertRaises(GraphError):
            normalize_edges(None)


class TestErrors(unittest.TestCase):
    def test_graph_error_is_erro(self):
        self.assertTrue(issubclass(GraphError, Erro))

    def test_cut_error_is_erro(self):
        self.assertTrue(issubclass(CutError, Erro))

    def test_erro_catches_all(self):
        try:
            normalize_edges([(0, 1)])
        except Erro:
            pass
        else:
            self.fail("expected Erro")


class TestMinCutTools(unittest.TestCase):
    def test_matches_plain(self):
        tools = MinCutTools(CLIQUE4)
        self.assertEqual(tools.global_min_cut(), pairwise_min_cut_value(CLIQUE4))

    def test_node_count(self):
        self.assertEqual(MinCutTools(PATH_GRAPH).node_count(), 3)

    def test_augment_count_grows_and_resets(self):
        tools = MinCutTools(CLIQUE4)
        tools.reset_augment_count()
        self.assertEqual(tools.augment_count(), 0)
        tools.global_min_cut()
        after = tools.augment_count()
        self.assertGreater(after, 0)
        tools.reset_augment_count()
        self.assertEqual(tools.augment_count(), 0)
        tools.global_min_cut()
        self.assertEqual(tools.augment_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = MinCutTools(CLIQUE4)
        b = MinCutTools(CLIQUE4)
        a.global_min_cut()
        self.assertEqual(b.augment_count(), 0)

    def test_exhaustive_method_matches(self):
        tools = MinCutTools(STAR_GRAPH)
        self.assertEqual(tools.exhaustive_min_cut(), tools.global_min_cut())


if __name__ == "__main__":
    unittest.main()
