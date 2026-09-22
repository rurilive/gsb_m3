"""DiGraph 的行为基线。"""

import unittest

from topoflow.graph import DiGraph


class TestDiGraph(unittest.TestCase):
    def test_add_node_reports_novelty(self):
        g = DiGraph()
        self.assertTrue(g.add_node("a"))
        self.assertFalse(g.add_node("a"))
        self.assertTrue(g.has_node("a"))

    def test_add_edge_creates_missing_nodes(self):
        g = DiGraph()
        self.assertTrue(g.add_edge("a", "b"))
        self.assertEqual(g.nodes(), ["a", "b"])
        self.assertEqual(g.edge_count(), 1)

    def test_duplicate_edge_is_ignored(self):
        g = DiGraph()
        g.add_edge("a", "b")
        self.assertFalse(g.add_edge("a", "b"))
        self.assertEqual(g.edge_count(), 1)
        self.assertEqual(g.in_degree("b"), 1)

    def test_remove_edge_reports_novelty(self):
        g = DiGraph()
        g.add_edge("a", "b")
        self.assertTrue(g.remove_edge("a", "b"))
        self.assertFalse(g.remove_edge("a", "b"))
        self.assertFalse(g.remove_edge("a", "zzz"))
        self.assertEqual(g.in_degree("b"), 0)

    def test_nodes_keep_registration_order(self):
        g = DiGraph()
        for node in ("z", "a", "m"):
            g.add_node(node)
        self.assertEqual(g.nodes(), ["z", "a", "m"])

    def test_edges_follow_source_order(self):
        g = DiGraph()
        g.add_edge("a", "c")
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        self.assertEqual(g.edges(), [("a", "c"), ("a", "b"), ("b", "c")])

    def test_neighbours_and_degrees(self):
        g = DiGraph()
        g.add_edge("a", "c")
        g.add_edge("b", "c")
        self.assertEqual(g.predecessors("c"), ["a", "b"])
        self.assertEqual(g.in_degree("c"), 2)
        self.assertEqual(g.out_degree("a"), 1)
        self.assertEqual(g.predecessors("nobody"), [])


if __name__ == "__main__":
    unittest.main()
