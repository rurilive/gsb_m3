"""Graph 现有行为的锁定测试。

这些用例锁住改造前的现状：只有节点、边与可达性，没有强连通分量、
拓扑、桥割点与最短路。测试一个字不改，改造后必须仍然全绿。
"""

import unittest

from graphiq.graph import (
    Graph,
    UnknownNode,
)


def build(nodes=None, edges=None):
    return Graph(nodes=nodes, edges=edges)


class TestBuild(unittest.TestCase):
    def test_nodes_in_insertion_order(self):
        g = build(["a", "b", "c"], [("a", "b")])
        self.assertEqual(g.nodes(), ["a", "b", "c"])

    def test_add_node_is_idempotent(self):
        g = build(["a"])
        g.add_node("a")
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])

    def test_has_node(self):
        g = build(["a"], [("a", "b")])
        self.assertTrue(g.has_node("a"))
        self.assertTrue(g.has_node("b"))
        self.assertFalse(g.has_node("z"))

    def test_edges_sorted_and_complete(self):
        g = build(edges=[("b", "c"), ("a", "b"), ("a", "c")])
        self.assertEqual(g.edges(), [("a", "b", 1.0), ("a", "c", 1.0),
                                     ("b", "c", 1.0)])

    def test_has_edge(self):
        g = build(edges=[("a", "b")])
        self.assertTrue(g.has_edge("a", "b"))
        self.assertFalse(g.has_edge("b", "a"))
        self.assertFalse(g.has_edge("a", "z"))

    def test_add_edge_lazily_registers_endpoints(self):
        g = build()
        g.add_edge("x", "y")
        self.assertEqual(g.nodes(), ["x", "y"])
        self.assertTrue(g.has_edge("x", "y"))

    def test_weight_defaults_to_one(self):
        g = build(edges=[("a", "b")])
        self.assertEqual(g.weight("a", "b"), 1.0)

    def test_weight(self):
        g = build(edges=[("a", "b", 2.5)])
        self.assertEqual(g.weight("a", "b"), 2.5)
        self.assertIsNone(g.weight("b", "a"))
        self.assertIsNone(g.weight("a", "z"))

    def test_duplicate_edge_overwrites(self):
        g = build(edges=[("a", "b", 1.0), ("a", "b", 7.0)])
        self.assertEqual(g.weight("a", "b"), 7.0)
        self.assertEqual(g.edges(), [("a", "b", 7.0)])

    def test_neighbors_sorted(self):
        g = build(edges=[("a", "c"), ("a", "b")])
        self.assertEqual(g.neighbors("a"), ["b", "c"])

    def test_neighbors_of_unknown_raises(self):
        g = build(["a"])
        with self.assertRaises(UnknownNode):
            g.neighbors("ghost")


class TestWeightValidation(unittest.TestCase):
    def test_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            build(edges=[("a", "b", -1.0)])

    def test_non_numeric_weight_raises(self):
        with self.assertRaises(ValueError):
            build(edges=[("a", "b", "x")])

    def test_bool_weight_raises(self):
        with self.assertRaises(ValueError):
            build(edges=[("a", "b", True)])

    def test_zero_weight_is_allowed(self):
        g = build(edges=[("a", "b", 0)])
        self.assertEqual(g.weight("a", "b"), 0)

    def test_self_loop_is_allowed(self):
        g = build(edges=[("a", "a", 3.0)])
        self.assertTrue(g.has_edge("a", "a"))
        self.assertEqual(g.weight("a", "a"), 3.0)


class TestReachable(unittest.TestCase):
    def test_reachable_includes_source(self):
        g = build(edges=[("a", "b"), ("b", "c")])
        self.assertEqual(g.reachable("a"), {"a", "b", "c"})

    def test_reachable_respects_direction(self):
        g = build(edges=[("a", "b")])
        self.assertEqual(g.reachable("b"), {"b"})

    def test_reachable_isolated_node(self):
        g = build(["a", "b"], [("a", "b")])
        self.assertEqual(g.reachable("b"), {"b"})

    def test_reachable_with_cycle_is_finite(self):
        g = build(edges=[("a", "b"), ("b", "c"), ("c", "a")])
        self.assertEqual(g.reachable("a"), {"a", "b", "c"})

    def test_reachable_unknown_raises(self):
        g = build(["a"])
        with self.assertRaises(UnknownNode):
            g.reachable("ghost")


class TestReachableAll(unittest.TestCase):
    def test_all_pairs_on_chain(self):
        g = build(edges=[("a", "b"), ("b", "c")])
        self.assertEqual(g.reachable_all(), {
            "a": {"a", "b", "c"},
            "b": {"b", "c"},
            "c": {"c"},
        })

    def test_all_pairs_on_cycle(self):
        g = build(edges=[("a", "b"), ("b", "a")])
        self.assertEqual(g.reachable_all(), {
            "a": {"a", "b"},
            "b": {"a", "b"},
        })

    def test_all_pairs_covers_every_node(self):
        g = build(["a", "b", "c"], [("a", "b")])
        result = g.reachable_all()
        self.assertEqual(set(result), {"a", "b", "c"})
        self.assertEqual(result["c"], {"c"})

    def test_all_pairs_ignores_weights(self):
        g = build(edges=[("a", "b", 5.0), ("a", "c", 0.0)])
        result = g.reachable_all()
        self.assertEqual(result["a"], {"a", "b", "c"})


if __name__ == "__main__":
    unittest.main()