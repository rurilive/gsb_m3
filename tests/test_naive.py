"""mincut 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from mincut.naive import (
    CutTools,
    GraphError,
    Erro,
    edge_subset_count,
    feasible_cut,
    global_min_cut_value,
    is_cut,
    min_cut,
    min_cut_value,
    reachable,
)


# 一张小型有向图：源点零，汇点三，最小割容量为四，割边编号一与二。
DIRECTED_GRAPH = [
    (0, 1, 3, 0),
    (0, 2, 2, 1),
    (1, 3, 2, 2),
    (2, 3, 3, 3),
]

# 一对反向边：有向口径最小割是三，无向口径最小割是六。
ANTI_PARALLEL = [
    (0, 1, 3, 0),
    (1, 0, 3, 1),
]


class TestMinCutDirected(unittest.TestCase):
    def test_capacity_and_edges(self):
        cut = min_cut(DIRECTED_GRAPH, 0, 3, directed=True)
        self.assertEqual(cut["capacity"], 4)
        self.assertEqual(cut["cut_edges"], [1, 2])
        self.assertEqual(sorted(cut["source_side"]), [0, 1])

    def test_value_matches_full(self):
        self.assertEqual(
            min_cut_value(DIRECTED_GRAPH, 0, 3, directed=True),
            min_cut(DIRECTED_GRAPH, 0, 3, directed=True)["capacity"])

    def test_parallel_and_zero_capacity(self):
        edges = [
            (0, 1, 2, 0),
            (0, 1, 3, 1),
            (1, 2, 0, 2),
        ]
        cut = min_cut(edges, 0, 2, directed=True)
        self.assertEqual(cut["capacity"], 0)
        self.assertEqual(cut["cut_edges"], [2])

    def test_single_edge(self):
        cut = min_cut([(0, 1, 9, 0)], 0, 1, directed=True)
        self.assertEqual(cut["capacity"], 9)
        self.assertEqual(cut["cut_edges"], [0])
        self.assertEqual(sorted(cut["source_side"]), [0])

    def test_unreachable_sink_gives_zero(self):
        cut = min_cut([(0, 1, 4, 0), (2, 3, 4, 1)], 0, 3, directed=True)
        self.assertEqual(cut["capacity"], 0)
        self.assertEqual(cut["cut_edges"], [])

    def test_source_equals_sink_rejected(self):
        with self.assertRaises(GraphError):
            min_cut(DIRECTED_GRAPH, 0, 0, directed=True)


class TestUndirected(unittest.TestCase):
    def test_undirected_min_cut(self):
        edges = [(0, 1, 1, 0), (1, 2, 2, 1), (0, 2, 3, 2)]
        cut = min_cut(edges, 0, 2, directed=False)
        self.assertEqual(cut["capacity"], 4)

    def test_undirected_differs_from_directed(self):
        directed = min_cut(ANTI_PARALLEL, 0, 1, directed=True)["capacity"]
        undirected = min_cut(ANTI_PARALLEL, 0, 1, directed=False)["capacity"]
        self.assertEqual(directed, 3)
        self.assertEqual(undirected, 6)

    def test_global_min_cut_value(self):
        edges = [(0, 1, 1, 0), (1, 2, 2, 1), (0, 2, 3, 2)]
        self.assertEqual(global_min_cut_value(edges), 3)

    def test_global_path_graph(self):
        edges = [(0, 1, 1, 0), (1, 2, 2, 1)]
        self.assertEqual(global_min_cut_value(edges), 1)

    def test_global_needs_two_nodes(self):
        with self.assertRaises(GraphError):
            global_min_cut_value([])


class TestIsCut(unittest.TestCase):
    def test_true_for_separator(self):
        self.assertTrue(is_cut(DIRECTED_GRAPH, 0, 3, {1, 2}, directed=True))

    def test_false_for_non_separator(self):
        self.assertFalse(is_cut(DIRECTED_GRAPH, 0, 3, {0}, directed=True))

    def test_unknown_edge_rejected(self):
        with self.assertRaises(GraphError):
            is_cut(DIRECTED_GRAPH, 0, 3, {99}, directed=True)

    def test_enumeration_of_separators(self):
        separators = []
        for mask in range(1 << 4):
            removed = {i for i in range(4) if mask >> i & 1}
            if is_cut(DIRECTED_GRAPH, 0, 3, removed, directed=True):
                separators.append(sorted(removed))
        self.assertIn([1, 2], separators)
        self.assertNotIn([], separators)
        self.assertEqual(len(separators), 9)


class TestFeasibleCut(unittest.TestCase):
    def test_within_budget(self):
        found = feasible_cut(DIRECTED_GRAPH, 0, 3, 4, directed=True)
        self.assertIsNotNone(found)
        self.assertEqual(found["capacity"], 4)

    def test_below_minimum(self):
        self.assertIsNone(
            feasible_cut(DIRECTED_GRAPH, 0, 3, 3, directed=True))

    def test_zero_capacity_graph_always_feasible(self):
        edges = [(0, 1, 0, 0), (1, 2, 0, 1), (0, 2, 0, 2)]
        found = feasible_cut(edges, 0, 2, 0, directed=True)
        self.assertIsNotNone(found)


class TestDeterminismAndEdges(unittest.TestCase):
    def test_repeated_run_same_result(self):
        first = min_cut(DIRECTED_GRAPH, 0, 3, directed=True)
        for _ in range(3):
            self.assertEqual(
                min_cut(DIRECTED_GRAPH, 0, 3, directed=True), first)

    def test_tie_breaks_lexicographically(self):
        edges = [
            (0, 1, 1, 5),
            (0, 1, 1, 2),
        ]
        self.assertEqual(
            min_cut(edges, 0, 1, directed=True)["cut_edges"], [2, 5])

    def test_self_loop_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 0, 1, 0)], 0, 1, directed=True)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 1, -1, 0)], 0, 1, directed=True)

    def test_duplicate_edge_id_rejected(self):
        with self.assertRaises(GraphError):
            min_cut([(0, 1, 1, 0), (1, 2, 1, 0)], 0, 2, directed=True)

    def test_bad_directed_flag_rejected(self):
        with self.assertRaises(GraphError):
            min_cut(DIRECTED_GRAPH, 0, 3, directed=1)

    def test_edge_subset_count(self):
        self.assertEqual(edge_subset_count(DIRECTED_GRAPH), 16)

    def test_reachable_with_blocked(self):
        arcs = [(0, 1, 1, 0), (1, 2, 1, 1)]
        self.assertEqual(reachable(arcs, 0, set(), True), {0, 1, 2})
        self.assertEqual(reachable(arcs, 0, {0}, True), {0})

    def test_graph_error_is_erro(self):
        self.assertTrue(issubclass(GraphError, Erro))

    def test_erro_catches_all(self):
        try:
            min_cut(DIRECTED_GRAPH, 0, 0, directed=True)
        except Erro:
            pass
        else:
            self.fail("expected Erro")


class TestCutTools(unittest.TestCase):
    def test_matches_plain(self):
        tools = CutTools(DIRECTED_GRAPH, directed=True)
        self.assertEqual(
            tools.min_cut(0, 3)["capacity"],
            min_cut(DIRECTED_GRAPH, 0, 3, directed=True)["capacity"])

    def test_subset_count_grows_and_resets(self):
        tools = CutTools(DIRECTED_GRAPH, directed=True)
        tools.reset_subset_count()
        self.assertEqual(tools.subset_count(), 0)
        tools.min_cut(0, 3)
        after = tools.subset_count()
        self.assertGreater(after, 0)
        tools.reset_subset_count()
        self.assertEqual(tools.subset_count(), 0)
        tools.min_cut(0, 3)
        self.assertEqual(tools.subset_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = CutTools(DIRECTED_GRAPH, directed=True)
        b = CutTools(DIRECTED_GRAPH, directed=True)
        a.min_cut(0, 3)
        self.assertEqual(b.subset_count(), 0)

    def test_directed_accessor(self):
        self.assertTrue(CutTools(DIRECTED_GRAPH, directed=True).directed())
        self.assertFalse(CutTools(DIRECTED_GRAPH, directed=False).directed())

    def test_is_cut_method(self):
        tools = CutTools(DIRECTED_GRAPH, directed=True)
        self.assertTrue(tools.is_cut(0, 3, {1, 2}))
        self.assertFalse(tools.is_cut(0, 3, {0}))

    def test_feasible_cut_method(self):
        tools = CutTools(DIRECTED_GRAPH, directed=True)
        self.assertIsNotNone(tools.feasible_cut(0, 3, 4))
        self.assertIsNone(tools.feasible_cut(0, 3, 3))


if __name__ == "__main__":
    unittest.main()
