"""flownet 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from flownet.naive import (
    Erro,
    FlowNetwork,
    FlowTools,
    GraphError,
    edge_subset_count,
    feasible_cut,
    is_cut,
    max_flow,
    min_cut,
    min_cut_value,
    reachable,
)


# 一张小型有向图：源点零，汇点三，最大流与最小割容量都是四，割边编号一与二。
DIRECTED_GRAPH = [
    (0, 1, 3, 0),
    (0, 2, 2, 1),
    (1, 3, 2, 2),
    (2, 3, 3, 3),
]

# 一对反向边：有向口径下从零到一只有一条正向边，容量为三。
ANTI_PARALLEL = [
    (0, 1, 3, 0),
    (1, 0, 3, 1),
]


class TestNaiveMaxFlow(unittest.TestCase):
    def test_value_and_augmentations(self):
        result = max_flow(DIRECTED_GRAPH, 0, 3)
        self.assertEqual(result.value, 4)
        self.assertEqual(result.augmentations, 2)

    def test_flows_non_negative_and_conserved(self):
        result = max_flow(DIRECTED_GRAPH, 0, 3)
        for _eid, amount in result.flows:
            self.assertGreaterEqual(amount, 0)
        self.assertEqual(dict(result.flows), {0: 2, 1: 2, 2: 2, 3: 2})

    def test_unreachable_sink_gives_zero(self):
        result = max_flow([(0, 1, 4, 0), (2, 3, 4, 1)], 0, 3)
        self.assertEqual(result.value, 0)
        self.assertEqual(result.augmentations, 0)

    def test_single_edge(self):
        result = max_flow([(0, 1, 9, 0)], 0, 1)
        self.assertEqual(result.value, 9)
        self.assertEqual(result.augmentations, 1)

    def test_source_equals_sink_rejected(self):
        with self.assertRaises(GraphError):
            max_flow(DIRECTED_GRAPH, 0, 0)

    def test_parallel_edges_and_capacity(self):
        edges = [(0, 1, 2, 0), (0, 1, 3, 1), (1, 2, 4, 2)]
        result = max_flow(edges, 0, 2)
        self.assertEqual(result.value, 4)
        self.assertEqual(result.augmentations, 2)


class TestNaiveMinCut(unittest.TestCase):
    def test_capacity_and_edges(self):
        cut = min_cut(DIRECTED_GRAPH, 0, 3)
        self.assertEqual(cut["capacity"], 4)
        self.assertEqual(cut["cut_edges"], [1, 2])
        self.assertEqual(sorted(cut["source_side"]), [0, 1])

    def test_value_matches_full(self):
        self.assertEqual(
            min_cut_value(DIRECTED_GRAPH, 0, 3),
            min_cut(DIRECTED_GRAPH, 0, 3)["capacity"])

    def test_max_flow_value_equals_min_cut(self):
        self.assertEqual(
            max_flow(DIRECTED_GRAPH, 0, 3).value,
            min_cut_value(DIRECTED_GRAPH, 0, 3))

    def test_parallel_and_zero_capacity(self):
        edges = [(0, 1, 2, 0), (0, 1, 3, 1), (1, 2, 0, 2)]
        cut = min_cut(edges, 0, 2)
        self.assertEqual(cut["capacity"], 0)
        self.assertEqual(cut["cut_edges"], [2])

    def test_single_edge(self):
        cut = min_cut([(0, 1, 9, 0)], 0, 1)
        self.assertEqual(cut["capacity"], 9)
        self.assertEqual(cut["cut_edges"], [0])
        self.assertEqual(sorted(cut["source_side"]), [0])

    def test_unreachable_sink_gives_zero(self):
        cut = min_cut([(0, 1, 4, 0), (2, 3, 4, 1)], 0, 3)
        self.assertEqual(cut["capacity"], 0)
        self.assertEqual(cut["cut_edges"], [])

    def test_source_equals_sink_rejected(self):
        with self.assertRaises(GraphError):
            min_cut(DIRECTED_GRAPH, 0, 0)

    def test_anti_parallel_only_forward_counts(self):
        cut = min_cut(ANTI_PARALLEL, 0, 1)
        self.assertEqual(cut["capacity"], 3)
        self.assertEqual(cut["cut_edges"], [0])


class TestIsCut(unittest.TestCase):
    def test_true_for_separator(self):
        self.assertTrue(is_cut(DIRECTED_GRAPH, 0, 3, {1, 2}))

    def test_false_for_non_separator(self):
        self.assertFalse(is_cut(DIRECTED_GRAPH, 0, 3, {0}))

    def test_unknown_edge_rejected(self):
        with self.assertRaises(GraphError):
            is_cut(DIRECTED_GRAPH, 0, 3, {99})

    def test_enumeration_of_separators(self):
        separators = []
        for mask in range(1 << 4):
            removed = {i for i in range(4) if mask >> i & 1}
            if is_cut(DIRECTED_GRAPH, 0, 3, removed):
                separators.append(sorted(removed))
        self.assertIn([1, 2], separators)
        self.assertNotIn([], separators)
        self.assertEqual(len(separators), 9)


class TestFeasibleCut(unittest.TestCase):
    def test_within_budget(self):
        found = feasible_cut(DIRECTED_GRAPH, 0, 3, 4)
        self.assertIsNotNone(found)
        self.assertEqual(found["capacity"], 4)

    def test_below_minimum(self):
        self.assertIsNone(feasible_cut(DIRECTED_GRAPH, 0, 3, 3))

    def test_zero_capacity_graph_always_feasible(self):
        edges = [(0, 1, 0, 0), (1, 2, 0, 1), (0, 2, 0, 2)]
        found = feasible_cut(edges, 0, 2, 0)
        self.assertIsNotNone(found)


class TestGraphAndEdges(unittest.TestCase):
    def test_repeated_run_same_result(self):
        first = min_cut(DIRECTED_GRAPH, 0, 3)
        for _ in range(3):
            self.assertEqual(min_cut(DIRECTED_GRAPH, 0, 3), first)

    def test_tie_breaks_lexicographically(self):
        edges = [(0, 1, 1, 5), (0, 1, 1, 2)]
        self.assertEqual(min_cut(edges, 0, 1)["cut_edges"], [2, 5])

    def test_self_loop_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 0, 1, 0)], 0, 1)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 1, -1, 0)], 0, 1)

    def test_duplicate_edge_id_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 1, 1, 0), (1, 2, 1, 0)], 0, 2)

    def test_bad_edge_length_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 1)], 0, 1)

    def test_edge_subset_count(self):
        self.assertEqual(edge_subset_count(DIRECTED_GRAPH), 16)

    def test_reachable_with_blocked(self):
        arcs = [(0, 1, 1, 0), (1, 2, 1, 1)]
        self.assertEqual(reachable(arcs, 0, set()), {0, 1, 2})
        self.assertEqual(reachable(arcs, 0, {0}), {0})

    def test_graph_error_is_erro(self):
        self.assertTrue(issubclass(GraphError, Erro))

    def test_erro_catches_all(self):
        try:
            min_cut(DIRECTED_GRAPH, 0, 0)
        except Erro:
            pass
        else:
            self.fail("expected Erro")


class TestFlowNetwork(unittest.TestCase):
    def test_augment_once_then_reset(self):
        network = FlowNetwork(DIRECTED_GRAPH)
        pushed = network.augment_once(0, 3)
        self.assertEqual(pushed, 2)
        self.assertEqual(network.value(0), 2)
        network.reset_flow()
        self.assertEqual(network.value(0), 0)

    def test_nodes_and_edges(self):
        network = FlowNetwork(DIRECTED_GRAPH)
        self.assertEqual(network.nodes(), [0, 1, 2, 3])
        self.assertEqual(network.edge_count(), 4)

    def test_reachable_from_residual(self):
        network = FlowNetwork(DIRECTED_GRAPH)
        network.augment_once(0, 3)
        self.assertEqual(network.reachable_from(0), {0, 1, 2, 3})


class TestFlowTools(unittest.TestCase):
    def test_matches_plain(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        self.assertEqual(tools.max_flow().value, max_flow(DIRECTED_GRAPH, 0, 3).value)
        self.assertEqual(
            tools.min_cut()["capacity"], min_cut(DIRECTED_GRAPH, 0, 3)["capacity"])

    def test_augment_count_grows_and_resets(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        tools.reset_augment_count()
        self.assertEqual(tools.augment_count(), 0)
        tools.max_flow()
        after = tools.augment_count()
        self.assertGreater(after, 0)
        tools.reset_augment_count()
        self.assertEqual(tools.augment_count(), 0)
        tools.max_flow()
        self.assertEqual(tools.augment_count(), after)

    def test_subset_count_grows_and_resets(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        tools.reset_subset_count()
        self.assertEqual(tools.subset_count(), 0)
        tools.min_cut()
        after = tools.subset_count()
        self.assertGreater(after, 0)
        tools.reset_subset_count()
        self.assertEqual(tools.subset_count(), 0)
        tools.min_cut()
        self.assertEqual(tools.subset_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = FlowTools(DIRECTED_GRAPH, 0, 3)
        b = FlowTools(DIRECTED_GRAPH, 0, 3)
        a.max_flow()
        a.min_cut()
        self.assertEqual(b.augment_count(), 0)
        self.assertEqual(b.subset_count(), 0)

    def test_source_and_sink_accessors(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        self.assertEqual(tools.source(), 0)
        self.assertEqual(tools.sink(), 3)

    def test_is_cut_method(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        self.assertTrue(tools.is_cut({1, 2}))
        self.assertFalse(tools.is_cut({0}))

    def test_feasible_cut_method(self):
        tools = FlowTools(DIRECTED_GRAPH, 0, 3)
        self.assertIsNotNone(tools.feasible_cut(4))
        self.assertIsNone(tools.feasible_cut(3))


if __name__ == "__main__":
    unittest.main()
