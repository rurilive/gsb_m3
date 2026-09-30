"""gomoryhu 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from gomoryhu.core import (
    Erro,
    GomoryHu,
    GraphError,
    UnknownNodeError,
)


# 两点一条边，最小割等于这条边的容量。
TWO_NODES = [(0, 1, 7)]

# 一条链：0 连 1 容量五，1 连 2 容量九。
CHAIN = [(0, 1, 5), (1, 2, 9)]

# 星形：中心零连三片叶子，容量分别二、三、四。
STAR = [(0, 1, 2), (0, 2, 3), (0, 3, 4)]

# 完全图，四条点两两相连，容量全为一。
COMPLETE = [
    (0, 1, 1),
    (0, 2, 1),
    (0, 3, 1),
    (1, 2, 1),
    (1, 3, 1),
    (2, 3, 1),
]


class TestPairCut(unittest.TestCase):
    def test_two_nodes(self):
        graph = GomoryHu(TWO_NODES)
        self.assertEqual(graph.pair_cut(0, 1)["value"], 7)
        self.assertEqual(graph.pair_cut(0, 1)["side"], [0])

    def test_chain(self):
        graph = GomoryHu(CHAIN)
        self.assertEqual(graph.pair_cut(0, 2)["value"], 5)
        self.assertEqual(graph.pair_cut(0, 1)["value"], 5)
        self.assertEqual(graph.pair_cut(1, 2)["value"], 9)

    def test_star(self):
        graph = GomoryHu(STAR)
        self.assertEqual(graph.pair_cut(1, 2)["value"], 2)
        self.assertEqual(graph.pair_cut(2, 3)["value"], 3)
        self.assertEqual(graph.pair_cut(1, 3)["value"], 2)

    def test_complete(self):
        graph = GomoryHu(COMPLETE)
        for i in range(4):
            for j in range(i + 1, 4):
                self.assertEqual(graph.pair_cut(i, j)["value"], 3)

    def test_parallel_edges_sum(self):
        graph = GomoryHu([(0, 1, 3), (0, 1, 4)])
        self.assertEqual(graph.pair_cut(0, 1)["value"], 7)

    def test_separate_components(self):
        graph = GomoryHu([(0, 1, 3), (2, 3, 4)])
        self.assertEqual(graph.pair_cut(0, 2)["value"], 0)
        self.assertEqual(graph.pair_cut(1, 3)["value"], 0)

    def test_zero_capacity_edge(self):
        graph = GomoryHu([(0, 1, 0), (1, 2, 5)])
        self.assertEqual(graph.pair_cut(0, 2)["value"], 0)


class TestAllPairs(unittest.TestCase):
    def test_matches_pairwise(self):
        graph = GomoryHu(STAR)
        full = graph.all_pairs_cuts()
        for (u, v), value in full.items():
            self.assertEqual(graph.pair_cut(u, v)["value"], value)

    def test_pair_ordering(self):
        graph = GomoryHu(COMPLETE)
        self.assertEqual(
            list(graph.all_pairs_cuts().keys()),
            [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
        )

    def test_single_node_has_no_pairs(self):
        graph = GomoryHu([(0, 1, 1)])
        self.assertEqual(GomoryHu([]).node_count(), 0)
        self.assertEqual(GomoryHu([]).all_pairs_cuts(), {})
        self.assertEqual(graph.node_count(), 2)


class TestPairDisjoint(unittest.TestCase):
    def test_chain_middle_separates(self):
        graph = GomoryHu(CHAIN)
        self.assertTrue(graph.pair_disjoint(0, 2, 1))

    def test_leaf_does_not_separate(self):
        graph = GomoryHu(CHAIN)
        self.assertFalse(graph.pair_disjoint(0, 1, 2))

    def test_star_center_separates_leaves(self):
        graph = GomoryHu(STAR)
        self.assertTrue(graph.pair_disjoint(1, 2, 0))
        self.assertFalse(graph.pair_disjoint(1, 0, 2))


class TestNodesAndEdges(unittest.TestCase):
    def test_nodes_sorted(self):
        graph = GomoryHu([(3, 1, 2), (2, 0, 4)])
        self.assertEqual(graph.nodes(), [0, 1, 2, 3])

    def test_has_edge(self):
        graph = GomoryHu(STAR)
        self.assertTrue(graph.has_edge(0, 1))
        self.assertTrue(graph.has_edge(1, 0))
        self.assertFalse(graph.has_edge(1, 2))


class TestErrors(unittest.TestCase):
    def test_source_equals_sink(self):
        with self.assertRaises(GraphError):
            GomoryHu(CHAIN).pair_cut(1, 1)

    def test_unknown_node(self):
        with self.assertRaises(UnknownNodeError):
            GomoryHu(CHAIN).pair_cut(0, 9)

    def test_self_loop_rejected(self):
        with self.assertRaises(GraphError):
            GomoryHu([(0, 0, 1)])

    def test_negative_capacity_rejected(self):
        with self.assertRaises(GraphError):
            GomoryHu([(0, 1, -1)])

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(GraphError):
            GomoryHu([(0, 1)])

    def test_all_errors_share_base(self):
        self.assertTrue(issubclass(GraphError, Erro))
        self.assertTrue(issubclass(UnknownNodeError, Erro))
        try:
            GomoryHu(CHAIN).pair_cut(0, 9)
        except Erro:
            pass
        else:
            self.fail("expected Erro")


class TestDeterminismAndCount(unittest.TestCase):
    def test_repeated_run_same_result(self):
        graph = GomoryHu(COMPLETE)
        first = graph.all_pairs_cuts()
        for _ in range(3):
            self.assertEqual(graph.all_pairs_cuts(), first)

    def test_augment_count_grows_and_resets(self):
        graph = GomoryHu(CHAIN)
        graph.reset_augment_count()
        self.assertEqual(graph.augment_count(), 0)
        graph.pair_cut(0, 2)
        after = graph.augment_count()
        self.assertGreater(after, 0)
        graph.reset_augment_count()
        self.assertEqual(graph.augment_count(), 0)
        graph.pair_cut(0, 2)
        self.assertEqual(graph.augment_count(), after)

    def test_edges_argument_narrows_graph(self):
        graph = GomoryHu(COMPLETE)
        kept = [(0, 1, 1), (1, 2, 1)]
        self.assertEqual(graph.pair_cut(0, 2, edges=kept)["value"], 1)
        self.assertEqual(graph.pair_cut(0, 3, edges=kept)["value"], 0)


if __name__ == "__main__":
    unittest.main()
