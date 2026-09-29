"""基线行为测试：锁住 ReachMatrix 的无权连通能力。"""

import unittest

from graphex.matrix import GraphError, ReachMatrix, UnknownNode


class ReachMatrixTest(unittest.TestCase):
    def _line(self):
        g = ReachMatrix(["a", "b", "c", "d"])
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        return g

    def test_add_node_is_idempotent(self):
        g = ReachMatrix(["a"])
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])

    def test_rejects_empty_name(self):
        g = ReachMatrix()
        with self.assertRaises(GraphError):
            g.add_node("")

    def test_edge_is_undirected(self):
        g = self._line()
        self.assertTrue(g.has_edge("a", "b"))
        self.assertTrue(g.has_edge("b", "a"))

    def test_reached_from_is_sorted(self):
        g = self._line()
        self.assertEqual(g.reached_from("a"), ["a", "b", "c"])

    def test_disconnected_node_absent(self):
        g = self._line()
        self.assertNotIn("d", g.reached_from("a"))

    def test_connected_reflexive(self):
        g = self._line()
        self.assertTrue(g.connected("a", "a"))

    def test_connected_across_path(self):
        g = self._line()
        self.assertTrue(g.connected("a", "c"))
        self.assertFalse(g.connected("a", "d"))

    def test_unknown_node_raises(self):
        g = self._line()
        with self.assertRaises(UnknownNode):
            g.reached_from("z")


if __name__ == "__main__":
    unittest.main()
