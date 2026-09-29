"""朴素连通判定现有行为的锁定测试（基线，一字不改）。

锁死改造前的口径：登记节点、加无向边、每次查询现场做一遍广度优先遍历，
组件成员按登记顺序、组件数把所有孤立节点各算一个。
"""

import unittest

from unionx import NaiveUnionFind, UnknownNode


class TestNaiveUnionFind(unittest.TestCase):
    def make(self):
        uf = NaiveUnionFind()
        for name in ("a", "b", "c", "d", "e"):
            uf.add_node(name)
        return uf

    def test_add_node_is_idempotent(self):
        uf = self.make()
        uf.add_node("a")
        self.assertEqual(uf.nodes(), ("a", "b", "c", "d", "e"))

    def test_has_node(self):
        uf = self.make()
        self.assertTrue(uf.has_node("a"))
        self.assertFalse(uf.has_node("z"))

    def test_nodes_in_insertion_order(self):
        uf = NaiveUnionFind()
        uf.add_node("x")
        uf.add_node("y")
        uf.add_node("z")
        self.assertEqual(uf.nodes(), ("x", "y", "z"))

    def test_isolated_nodes_not_connected(self):
        uf = self.make()
        self.assertFalse(uf.connected("a", "b"))

    def test_node_connected_to_itself(self):
        uf = self.make()
        self.assertTrue(uf.connected("a", "a"))

    def test_direct_edge_connected(self):
        uf = self.make()
        uf.add_edge("a", "b")
        self.assertTrue(uf.connected("a", "b"))
        self.assertTrue(uf.connected("b", "a"))

    def test_transitive_connectivity(self):
        uf = self.make()
        uf.add_edge("a", "b")
        uf.add_edge("b", "c")
        self.assertTrue(uf.connected("a", "c"))
        self.assertFalse(uf.connected("a", "d"))

    def test_duplicate_edge_is_noop(self):
        uf = self.make()
        uf.add_edge("a", "b")
        uf.add_edge("b", "a")
        self.assertEqual(uf.edges(), (("a", "b"),))

    def test_edges_in_insertion_order(self):
        uf = self.make()
        uf.add_edge("a", "b")
        uf.add_edge("c", "d")
        self.assertEqual(uf.edges(), (("a", "b"), ("c", "d")))

    def test_connected_unknown_node_raises(self):
        uf = self.make()
        with self.assertRaises(UnknownNode):
            uf.connected("a", "zzz")

    def test_add_edge_unknown_node_raises(self):
        uf = self.make()
        with self.assertRaises(UnknownNode):
            uf.add_edge("a", "zzz")

    def test_component_of_returns_insertion_order(self):
        uf = self.make()
        uf.add_edge("c", "a")
        uf.add_edge("a", "b")
        self.assertEqual(uf.component_of("a"), ("a", "b", "c"))

    def test_component_of_isolated(self):
        uf = self.make()
        self.assertEqual(uf.component_of("d"), ("d",))

    def test_component_count(self):
        uf = self.make()
        uf.add_edge("a", "b")
        self.assertEqual(uf.component_count(), 4)

    def test_component_count_all_isolated(self):
        uf = self.make()
        self.assertEqual(uf.component_count(), 5)

    def test_component_sizes_in_order(self):
        uf = self.make()
        uf.add_edge("a", "b")
        uf.add_edge("d", "e")
        self.assertEqual(uf.component_sizes(), (2, 1, 2))

    def test_component_sizes_empty(self):
        self.assertEqual(NaiveUnionFind().component_sizes(), ())

    def test_component_count_empty(self):
        self.assertEqual(NaiveUnionFind().component_count(), 0)


if __name__ == "__main__":
    unittest.main()
