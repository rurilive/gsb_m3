"""基线测试：锁住改造前 NaiveGraph 的现状行为。

这些用例描述的是当前"增广路深搜求匹配、左侧点子集枚举求覆盖"
实现对外可见的事实，改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from konig.graph import (
    DuplicateEdgeError,
    IllegalPointError,
    KonigError,
    NaiveGraph,
    NotMatchedError,
    SelfLoopError,
    UnknownPointError,
)


def _chain():
    """固定图：a-x、b-x、b-y、c-y。"""
    g = NaiveGraph(left=["a", "b", "c"], right=["x", "y"])
    g.add_edge("a", "x")
    g.add_edge("b", "x")
    g.add_edge("b", "y")
    g.add_edge("c", "y")
    return g


class TestGraphBuilding(unittest.TestCase):
    def test_empty_graph(self):
        g = NaiveGraph()
        self.assertEqual(g.left_points(), [])
        self.assertEqual(g.right_points(), [])
        self.assertEqual(g.edge_count(), 0)

    def test_register_points_is_idempotent(self):
        g = NaiveGraph()
        g.add_left("a").add_left("a")
        g.add_right("x").add_right("x")
        self.assertEqual(g.left_points(), ["a"])
        self.assertEqual(g.right_points(), ["x"])

    def test_edges_keep_insertion_order(self):
        g = _chain()
        self.assertEqual(g.edges(),
                         [("a", "x"), ("b", "x"), ("b", "y"), ("c", "y")])

    def test_neighbors_known_point(self):
        g = _chain()
        self.assertEqual(g.neighbors("b"), ["x", "y"])

    def test_neighbors_unknown_point_raises(self):
        g = _chain()
        with self.assertRaises(UnknownPointError):
            g.neighbors("nope")


class TestNaiveMatching(unittest.TestCase):
    def test_empty_graph_zero(self):
        g = NaiveGraph()
        self.assertEqual(g.naive_matching_size(), 0)
        self.assertEqual(g.naive_max_matching(), [])

    def test_no_edges_zero(self):
        g = NaiveGraph(left=["a", "b"], right=["x"])
        self.assertEqual(g.naive_matching_size(), 0)

    def test_single_edge(self):
        g = NaiveGraph(left=["l1"], right=["r1"])
        g.add_edge("l1", "r1")
        self.assertEqual(g.naive_max_matching(), [("l1", "r1")])
        self.assertEqual(g.naive_matching_size(), 1)

    def test_competing_lefts(self):
        g = NaiveGraph(left=["l1", "l2"], right=["r1"])
        g.add_edge("l1", "r1")
        g.add_edge("l2", "r1")
        self.assertEqual(g.naive_matching_size(), 1)

    def test_augmenting_case(self):
        # l1-r1、l2-r1、l2-r2：最大匹配应为 2。
        g = NaiveGraph(left=["l1", "l2"], right=["r1", "r2"])
        g.add_edge("l1", "r1")
        g.add_edge("l2", "r1")
        g.add_edge("l2", "r2")
        self.assertEqual(g.naive_matching_size(), 2)
        self.assertEqual(g.naive_max_matching(), [("l1", "r1"), ("l2", "r2")])

    def test_matched_to_after_search(self):
        g = NaiveGraph(left=["l1", "l2"], right=["r1", "r2"])
        g.add_edge("l1", "r1")
        g.add_edge("l2", "r2")
        self.assertEqual(g.naive_matching_size(), 2)
        self.assertEqual(g.matched_to("l1"), "r1")
        self.assertEqual(g.matched_to("l2"), "r2")

    def test_matched_to_before_search_raises(self):
        g = NaiveGraph(left=["l1"], right=["r1"])
        g.add_edge("l1", "r1")
        with self.assertRaises(KonigError):
            g.matched_to("l1")

    def test_matched_to_unmatched_raises(self):
        g = NaiveGraph(left=["l1", "l2"], right=["r1"])
        g.add_edge("l1", "r1")
        g.add_edge("l2", "r1")
        g.naive_matching_size()
        with self.assertRaises(NotMatchedError):
            g.matched_to("l2")

    def test_matched_to_unknown_raises(self):
        g = _chain()
        g.naive_matching_size()
        with self.assertRaises(UnknownPointError):
            g.matched_to("ghost")


class TestNaiveCover(unittest.TestCase):
    def test_empty_graph_cover(self):
        g = NaiveGraph()
        self.assertEqual(g.naive_min_vertex_cover(), [])

    def test_no_edges_cover_empty(self):
        g = NaiveGraph(left=["a", "b"], right=["x"])
        self.assertEqual(g.naive_min_vertex_cover(), [])
        self.assertEqual(g.naive_cover_size(), 0)

    def test_single_edge_cover(self):
        g = NaiveGraph(left=["l1"], right=["r1"])
        g.add_edge("l1", "r1")
        self.assertEqual(g.naive_min_vertex_cover(), ["l1"])

    def test_cover_only_uses_left_points(self):
        # 真正的两点覆盖是 {x, y}，但朴素做法只从左点里挑，只能给出全部左点。
        g = _chain()
        cover = g.naive_min_vertex_cover()
        self.assertEqual(cover, ["a", "b", "c"])
        self.assertTrue(all(point in g.left_points() for point in cover))

    def test_cover_covers_every_edge(self):
        g = _chain()
        cover = set(g.naive_min_vertex_cover())
        for left, right in g.edges():
            self.assertTrue(left in cover)


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(IllegalPointError, KonigError))
        self.assertTrue(issubclass(SelfLoopError, KonigError))
        self.assertTrue(issubclass(DuplicateEdgeError, KonigError))
        self.assertTrue(issubclass(UnknownPointError, KonigError))
        self.assertTrue(issubclass(NotMatchedError, KonigError))

    def test_empty_name_rejected(self):
        g = NaiveGraph()
        with self.assertRaises(IllegalPointError):
            g.add_left("")

    def test_unknown_point_rejected(self):
        g = NaiveGraph(left=["a"], right=["x"])
        with self.assertRaises(UnknownPointError):
            g.add_edge("z", "x")

    def test_self_loop_rejected(self):
        g = NaiveGraph(left=["v"], right=["v"])
        with self.assertRaises(SelfLoopError):
            g.add_edge("v", "v")

    def test_duplicate_edge_rejected(self):
        g = NaiveGraph(left=["a"], right=["x"])
        g.add_edge("a", "x")
        with self.assertRaises(DuplicateEdgeError):
            g.add_edge("a", "x")

    def test_fixed_graph_repeatable(self):
        def run():
            g = _chain()
            return (g.naive_max_matching(),
                    g.naive_min_vertex_cover(),
                    g.naive_matching_size())

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
