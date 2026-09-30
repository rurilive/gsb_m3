"""基线行为测试：锁住 NaiveMatcher 的朴素最大匹配能力。

这些测试断言的是改造前的现状：只报匹配边数与边集，不做覆盖、不做判定、
不记录搜索规模。基线一字不改，必须原样全绿。
"""

import unittest

from bipmatch.matcher import (
    BipMatchError,
    CannotMatchError,
    DuplicateEdgeError,
    NaiveMatcher,
    SelfLoopError,
)


def _perfect():
    """完全匹配的固定图：三条互不相交的边。"""
    m = NaiveMatcher(["a", "b", "c"], ["x", "y", "z"])
    m.add_edge("a", "x")
    m.add_edge("a", "y")
    m.add_edge("b", "y")
    m.add_edge("c", "z")
    return m


class GraphBuildingTest(unittest.TestCase):
    def test_add_vertex_is_idempotent(self):
        m = NaiveMatcher(["a"], ["x"])
        m.add_left("a")
        m.add_right("x")
        self.assertEqual(m.left_nodes(), ["a"])
        self.assertEqual(m.right_nodes(), ["x"])

    def test_rejects_empty_name(self):
        m = NaiveMatcher()
        with self.assertRaises(BipMatchError):
            m.add_left("")

    def test_edges_keep_insertion_order(self):
        m = _perfect()
        self.assertEqual(m.edges(),
                         [("a", "x"), ("a", "y"), ("b", "y"), ("c", "z")])

    def test_adjacency_lists_neighbours(self):
        m = NaiveMatcher(["a", "b"], ["x", "y"])
        m.add_edge("a", "x")
        m.add_edge("a", "y")
        m.add_edge("b", "x")
        self.assertEqual(m.adjacency(), {"a": ["x", "y"], "b": ["x"]})

    def test_unknown_left_rejected(self):
        m = NaiveMatcher(["a"], ["x"])
        with self.assertRaises(CannotMatchError):
            m.add_edge("z", "x")

    def test_unknown_right_rejected(self):
        m = NaiveMatcher(["a"], ["x"])
        with self.assertRaises(CannotMatchError):
            m.add_edge("a", "z")

    def test_self_loop_rejected(self):
        m = NaiveMatcher(["v"], ["v"])
        with self.assertRaises(SelfLoopError):
            m.add_edge("v", "v")

    def test_duplicate_edge_rejected(self):
        m = NaiveMatcher(["a"], ["x"])
        m.add_edge("a", "x")
        with self.assertRaises(DuplicateEdgeError):
            m.add_edge("a", "x")


class NaiveMatchingTest(unittest.TestCase):
    def test_size_on_perfect_graph(self):
        self.assertEqual(_perfect().match(), 3)

    def test_edges_on_perfect_graph(self):
        self.assertEqual(_perfect().matching_edges(),
                         [("a", "x"), ("b", "y"), ("c", "z")])

    def test_size_on_bipartite_chain(self):
        m = NaiveMatcher(["a", "b"], ["x", "y"])
        m.add_edge("a", "x")
        m.add_edge("a", "y")
        m.add_edge("b", "x")
        self.assertEqual(m.match(), 2)
        self.assertEqual(m.matching_edges(), [("a", "y"), ("b", "x")])

    def test_size_when_right_side_saturated(self):
        m = NaiveMatcher(["a", "b", "c"], ["x", "y"])
        m.add_edge("a", "x")
        m.add_edge("b", "x")
        m.add_edge("c", "x")
        self.assertEqual(m.match(), 1)
        self.assertEqual(m.matching_edges(), [("a", "x")])

    def test_empty_graph(self):
        m = NaiveMatcher(["a", "b"], ["x"])
        self.assertEqual(m.match(), 0)
        self.assertEqual(m.matching_edges(), [])

    def test_no_edges(self):
        m = NaiveMatcher(["a"], ["x", "y"])
        self.assertEqual(m.match(), 0)
        self.assertEqual(m.matching_edges(), [])

    def test_repeated_calls_agree(self):
        m = _perfect()
        first = m.matching_edges()
        second = m.matching_edges()
        self.assertEqual(first, second)
        self.assertEqual(m.match(), 3)


if __name__ == "__main__":
    unittest.main()
