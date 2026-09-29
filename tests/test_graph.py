"""DirectedWeightedGraph 现有行为的锁定测试。"""

import math
import unittest

from graphinc.graph import (
    CycleError,
    DirectedWeightedGraph,
    UnknownNode,
)


def build(nodes, edges):
    return DirectedWeightedGraph(nodes=nodes, edges=edges)


class TestBuild(unittest.TestCase):
    def test_nodes_in_insertion_order(self):
        g = build(["a", "b", "c"], [("a", "b", 1.0)])
        self.assertEqual(g.nodes(), ["a", "b", "c"])

    def test_add_node_is_idempotent(self):
        g = build(["a"], [])
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])

    def test_has_node(self):
        g = build(["a"], [("a", "b", 2.0)])
        self.assertTrue(g.has_node("a"))
        self.assertTrue(g.has_node("b"))
        self.assertFalse(g.has_node("z"))

    def test_edges_sorted_and_complete(self):
        g = build([], [("b", "c", 3.0), ("a", "b", 1.0), ("a", "c", 7.0)])
        self.assertEqual(g.edges(), [("a", "b", 1.0), ("a", "c", 7.0),
                                     ("b", "c", 3.0)])

    def test_has_edge(self):
        g = build([], [("a", "b", 1.0)])
        self.assertTrue(g.has_edge("a", "b"))
        self.assertFalse(g.has_edge("b", "a"))
        self.assertFalse(g.has_edge("a", "z"))

    def test_weight(self):
        g = build([], [("a", "b", 2.5)])
        self.assertEqual(g.weight("a", "b"), 2.5)
        self.assertIsNone(g.weight("b", "a"))
        self.assertIsNone(g.weight("a", "z"))

    def test_neighbors_sorted(self):
        g = build([], [("a", "c", 3.0), ("a", "b", 1.0)])
        self.assertEqual(g.neighbors("a"), [("b", 1.0), ("c", 3.0)])

    def test_neighbors_of_unknown_raises(self):
        g = build(["a"], [])
        with self.assertRaises(UnknownNode):
            g.neighbors("ghost")


class TestWeightValidation(unittest.TestCase):
    def test_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            build([], [("a", "b", -1.0)])

    def test_non_numeric_weight_raises(self):
        with self.assertRaises(ValueError):
            build([], [("a", "b", "x")])

    def test_bool_weight_raises(self):
        with self.assertRaises(ValueError):
            build([], [("a", "b", True)])

    def test_zero_weight_is_allowed(self):
        g = build([], [("a", "b", 0)])
        self.assertEqual(g.weight("a", "b"), 0)


class TestDistances(unittest.TestCase):
    def test_simple_chain(self):
        g = build([], [("a", "b", 1.0), ("b", "c", 2.0)])
        dist = g.distances("a")
        self.assertEqual(dist["a"], 0)
        self.assertEqual(dist["b"], 1.0)
        self.assertEqual(dist["c"], 3.0)

    def test_picks_shorter_route(self):
        g = build([], [("a", "b", 5.0), ("a", "c", 1.0), ("c", "b", 1.0)])
        self.assertEqual(g.distances("a")["b"], 2.0)

    def test_unreachable_is_inf(self):
        g = build(["a", "b"], [("a", "a", 0)])
        dist = g.distances("a")
        self.assertTrue(math.isinf(dist["b"]))

    def test_zero_weight_edge(self):
        g = build([], [("a", "b", 0), ("b", "c", 1.0)])
        self.assertEqual(g.distances("a")["c"], 1.0)

    def test_unknown_source_raises(self):
        g = build(["a"], [])
        with self.assertRaises(UnknownNode):
            g.distances("ghost")

    def test_result_is_a_copy(self):
        g = build([], [("a", "b", 1.0)])
        first = g.distances("a")
        first["b"] = 999
        self.assertEqual(g.distances("a")["b"], 1.0)


class TestShortestPath(unittest.TestCase):
    def test_path_and_distance(self):
        g = build([], [("a", "b", 1.0), ("b", "c", 2.0)])
        d, path = g.shortest_path("a", "c")
        self.assertEqual(d, 3.0)
        self.assertEqual(path, ["a", "b", "c"])

    def test_source_to_itself(self):
        g = build(["a"], [])
        self.assertEqual(g.shortest_path("a", "a"), (0, ["a"]))

    def test_unreachable_returns_inf_and_empty(self):
        g = build(["a", "b"], [])
        self.assertEqual(g.shortest_path("a", "b"), (math.inf, []))

    def test_unknown_target_raises(self):
        g = build(["a"], [])
        with self.assertRaises(UnknownNode):
            g.shortest_path("a", "ghost")


class TestReachable(unittest.TestCase):
    def test_reachable_includes_source(self):
        g = build([], [("a", "b", 1.0), ("b", "c", 1.0)])
        self.assertEqual(g.reachable("a"), {"a", "b", "c"})

    def test_reachable_respects_direction(self):
        g = build([], [("a", "b", 1.0)])
        self.assertEqual(g.reachable("b"), {"b"})


class TestTopoOrder(unittest.TestCase):
    def test_chain(self):
        g = build([], [("a", "b", 1.0), ("b", "c", 1.0)])
        self.assertEqual(g.topo_order(), ["a", "b", "c"])

    def test_diamond(self):
        g = build([], [("a", "b", 1.0), ("a", "c", 1.0),
                       ("b", "d", 1.0), ("c", "d", 1.0)])
        order = g.topo_order()
        self.assertEqual(order[0], "a")
        self.assertEqual(order[-1], "d")
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_deterministic(self):
        g = build([], [("a", "b", 1.0), ("a", "c", 1.0), ("b", "d", 1.0)])
        self.assertEqual(g.topo_order(), g.topo_order())

    def test_cycle_raises(self):
        g = build([], [("a", "b", 1.0), ("b", "a", 1.0)])
        with self.assertRaises(CycleError):
            g.topo_order()


if __name__ == "__main__":
    unittest.main()