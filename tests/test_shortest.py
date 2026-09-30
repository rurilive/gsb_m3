"""WeightedGraph 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from wgraph.shortest import WeightedGraph, UnknownNode, EdgeError


class TestBuild(unittest.TestCase):
    def test_add_node_idempotent(self):
        g = WeightedGraph()
        g.add_node("a")
        g.add_node("a")
        self.assertEqual(g.node_count(), 1)
        self.assertTrue(g.has_node("a"))

    def test_add_edge_registers_endpoints(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 3)
        self.assertEqual(g.node_count(), 2)
        self.assertEqual(g.edge_count(), 1)

    def test_directed_edge_is_one_way(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 3)
        self.assertEqual(g.neighbors("a"), [("b", 3)])
        self.assertEqual(g.neighbors("b"), [])

    def test_undirected_edge_is_two_way(self):
        g = WeightedGraph(directed=False)
        g.add_edge("a", "b", 3)
        self.assertEqual(sorted(g.neighbors("a")), [("b", 3)])
        self.assertEqual(sorted(g.neighbors("b")), [("a", 3)])

    def test_negative_weight_rejected(self):
        g = WeightedGraph()
        with self.assertRaises(EdgeError):
            g.add_edge("a", "b", -1)

    def test_non_int_weight_rejected(self):
        g = WeightedGraph()
        with self.assertRaises(EdgeError):
            g.add_edge("a", "b", 1.5)

    def test_bool_weight_rejected(self):
        g = WeightedGraph()
        with self.assertRaises(EdgeError):
            g.add_edge("a", "b", True)

    def test_unknown_node_neighbors(self):
        g = WeightedGraph()
        with self.assertRaises(UnknownNode):
            g.neighbors("ghost")

    def test_nodes_listing(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        g.add_node("c")
        self.assertEqual(sorted(g.nodes()), ["a", "b", "c"])

    def test_edge_error_is_value_error(self):
        self.assertTrue(issubclass(EdgeError, ValueError))

    def test_unknown_node_is_key_error(self):
        self.assertTrue(issubclass(UnknownNode, KeyError))


class TestShortestDistances(unittest.TestCase):
    def test_single_node(self):
        g = WeightedGraph()
        g.add_node("a")
        self.assertEqual(g.shortest_distances("a"), {"a": 0})

    def test_direct_edge(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 5)
        self.assertEqual(g.shortest_distances("a"), {"a": 0, "b": 5})

    def test_picks_cheaper_detour(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 10)
        g.add_edge("a", "c", 1)
        g.add_edge("c", "b", 2)
        dist = g.shortest_distances("a")
        self.assertEqual(dist["b"], 3)
        self.assertEqual(dist["c"], 1)

    def test_unreachable_is_none(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        g.add_node("z")
        dist = g.shortest_distances("a")
        self.assertIsNone(dist["z"])

    def test_zero_weight_edge(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 0)
        g.add_edge("b", "c", 4)
        self.assertEqual(g.shortest_distances("a")["c"], 4)

    def test_unknown_source_rejected(self):
        g = WeightedGraph()
        g.add_node("a")
        with self.assertRaises(UnknownNode):
            g.shortest_distances("ghost")


class TestShortestPredecessors(unittest.TestCase):
    def test_source_has_no_predecessor(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        pred = g.shortest_predecessors("a")
        self.assertIsNone(pred["a"])

    def test_predecessor_chain(self):
        g = WeightedGraph()
        g.add_edge("a", "c", 1)
        g.add_edge("c", "b", 2)
        g.add_edge("a", "b", 10)
        pred = g.shortest_predecessors("a")
        self.assertEqual(pred["b"], "c")
        self.assertEqual(pred["c"], "a")

    def test_unreachable_predecessor_is_none(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        g.add_node("z")
        self.assertIsNone(g.shortest_predecessors("a")["z"])


class TestShortestPath(unittest.TestCase):
    def test_path_to_self(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        self.assertEqual(g.shortest_path("a", "a"), ["a"])

    def test_path_uses_cheaper_route(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 10)
        g.add_edge("a", "c", 1)
        g.add_edge("c", "b", 2)
        self.assertEqual(g.shortest_path("a", "b"), ["a", "c", "b"])

    def test_unreachable_path_is_empty(self):
        g = WeightedGraph()
        g.add_edge("a", "b", 1)
        g.add_node("z")
        self.assertEqual(g.shortest_path("a", "z"), [])

    def test_unknown_target_rejected(self):
        g = WeightedGraph()
        g.add_node("a")
        with self.assertRaises(UnknownNode):
            g.shortest_path("a", "ghost")

    def test_undirected_round_trip(self):
        g = WeightedGraph(directed=False)
        g.add_edge("a", "b", 4)
        g.add_edge("b", "c", 6)
        self.assertEqual(g.shortest_path("c", "a"), ["c", "b", "a"])


if __name__ == "__main__":
    unittest.main()
