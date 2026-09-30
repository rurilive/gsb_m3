"""基线测试：锁住改造前 BipartiteMatcher 的现状行为。

这些用例描述的是当前"枚举驱动"实现对外可见的事实，改造成增广路之后
必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchx.bipartite import (
    BipartiteMatcher,
    InvalidEdgeError,
    MatchError,
    NotMatchedError,
    UnknownNodeError,
)


def build(edges):
    m = BipartiteMatcher()
    for left, right in edges:
        m.add_edge(left, right)
    return m


class TestBuild(unittest.TestCase):
    def test_empty_graph(self):
        m = BipartiteMatcher()
        self.assertEqual(m.left_nodes, [])
        self.assertEqual(m.right_nodes, [])
        self.assertEqual(m.edge_count(), 0)
        self.assertEqual(m.node_count(), 0)

    def test_add_edge_registers_points(self):
        m = BipartiteMatcher()
        m.add_edge("l1", "r1")
        self.assertEqual(m.left_nodes, ["l1"])
        self.assertEqual(m.right_nodes, ["r1"])
        self.assertEqual(m.edge_count(), 1)

    def test_add_edge_is_chainable(self):
        m = BipartiteMatcher()
        m.add_edge("l1", "r1").add_edge("l1", "r2")
        self.assertEqual(m.edge_count(), 2)
        self.assertEqual(m.neighbors("l1"), {"r1", "r2"})

    def test_duplicate_edge_counted_once(self):
        m = BipartiteMatcher()
        m.add_edge("l1", "r1")
        m.add_edge("l1", "r1")
        self.assertEqual(m.edge_count(), 1)

    def test_edges_sorted_stable(self):
        m = build([("l2", "r1"), ("l1", "r2"), ("l1", "r1")])
        self.assertEqual(m.edges(), [("l1", "r1"), ("l1", "r2"), ("l2", "r1")])

    def test_self_loop_rejected(self):
        m = BipartiteMatcher()
        with self.assertRaises(InvalidEdgeError):
            m.add_edge("x", "x")

    def test_none_endpoint_rejected(self):
        m = BipartiteMatcher()
        with self.assertRaises(InvalidEdgeError):
            m.add_edge("l1", None)

    def test_neighbors_unknown_point_raises(self):
        m = BipartiteMatcher()
        with self.assertRaises(UnknownNodeError):
            m.neighbors("nope")


class TestMaxMatchingSize(unittest.TestCase):
    def test_empty_graph_zero(self):
        self.assertEqual(BipartiteMatcher().max_matching_size(), 0)

    def test_no_edges_zero(self):
        m = BipartiteMatcher()
        m.add_edge("l1", "r1")
        self.assertEqual(BipartiteMatcher().max_matching_size(), 0)
        self.assertEqual(m.max_matching_size(), 1)

    def test_single_left_two_rights_takes_one(self):
        self.assertEqual(build([("l1", "r1"), ("l1", "r2")]).max_matching_size(), 1)

    def test_competing_lefts_share_one_right(self):
        self.assertEqual(build([("l1", "r1"), ("l2", "r1")]).max_matching_size(), 1)

    def test_augmenting_case(self):
        # l1-r1、l2-r1、l2-r2：最大匹配为 2。
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        self.assertEqual(m.max_matching_size(), 2)

    def test_complete_bipartite(self):
        m = build([("l1", "r1"), ("l1", "r2"), ("l2", "r1"), ("l2", "r2")])
        self.assertEqual(m.max_matching_size(), 2)

    def test_chain_graph(self):
        m = build([("l1", "r1"), ("l1", "r2"), ("l2", "r2"), ("l2", "r3")])
        self.assertEqual(m.max_matching_size(), 2)

    def test_isolated_right_points(self):
        m = build([("l1", "r1"), ("l2", "r2")])
        m.add_edge("l3", "r3")
        self.assertEqual(m.max_matching_size(), 3)

    def test_uneven_sides_limited_by_smaller(self):
        m = build([("l1", "r1"), ("l1", "r2"), ("l1", "r3")])
        self.assertEqual(m.max_matching_size(), 1)


class TestPerfectAndMaximum(unittest.TestCase):
    def test_empty_left_is_perfect(self):
        self.assertTrue(BipartiteMatcher().perfect_matching_exists())

    def test_left_larger_than_right_not_perfect(self):
        m = build([("l1", "r1"), ("l2", "r1")])
        self.assertFalse(m.perfect_matching_exists())

    def test_full_pairing_is_perfect(self):
        self.assertTrue(build([("l1", "r1"), ("l2", "r2")]).perfect_matching_exists())

    def test_is_maximum_true_for_largest(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        self.assertTrue(m.is_maximum({"l1": "r1", "l2": "r2"}))

    def test_is_maximum_false_for_smaller(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        self.assertFalse(m.is_maximum({"l2": "r1"}))

    def test_is_maximum_rejects_bad_right(self):
        m = build([("l1", "r1")])
        with self.assertRaises(UnknownNodeError):
            m.is_maximum({"l1": "r9"})

    def test_is_maximum_rejects_non_edge(self):
        m = build([("l1", "r1"), ("l2", "r2")])
        with self.assertRaises(MatchError):
            m.is_maximum({"l1": "r2"})

    def test_is_maximum_rejects_shared_right(self):
        m = build([("l1", "r1"), ("l2", "r1")])
        with self.assertRaises(MatchError):
            m.is_maximum({"l1": "r1", "l2": "r1"})


class TestMaxMatchingPlan(unittest.TestCase):
    def test_plan_size_matches(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        plan = m.max_matching()
        self.assertEqual(len(plan), m.max_matching_size())

    def test_plan_is_legal_matching(self):
        m = build([("l1", "r1"), ("l1", "r2"), ("l2", "r1")])
        plan = m.max_matching()
        self.assertEqual(len(set(plan.values())), len(plan))
        for left, right in plan.items():
            self.assertTrue(m.has_edge(left, right))

    def test_matched_to_unknown_left_raises(self):
        m = build([("l1", "r1")])
        with self.assertRaises(UnknownNodeError):
            m.matched_to("l9")

    def test_matched_to_unmatched_raises(self):
        m = build([("l1", "r1"), ("l2", "r1")])
        m.max_matching()
        with self.assertRaises(NotMatchedError):
            m.matched_to("l2")

    def test_matched_to_returns_partner(self):
        m = build([("l1", "r1")])
        m.max_matching()
        self.assertEqual(m.matched_to("l1"), "r1")


class TestCoverAndIndependent(unittest.TestCase):
    def test_empty_cover(self):
        self.assertEqual(BipartiteMatcher().min_vertex_cover(), [])

    def test_cover_of_single_edge(self):
        m = build([("l1", "r1")])
        self.assertEqual(len(m.min_vertex_cover()), 1)

    def test_cover_size_equals_matching_size(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        self.assertEqual(len(m.min_vertex_cover()), m.max_matching_size())

    def test_cover_covers_all_edges(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        cover = set(m.min_vertex_cover())
        for left, right in m.edges():
            self.assertTrue(left in cover or right in cover)

    def test_independent_of_single_edge(self):
        m = build([("l1", "r1")])
        self.assertEqual(len(m.max_independent_set()), 1)

    def test_independent_size_complement_of_cover(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        iset = m.max_independent_set()
        self.assertEqual(len(iset), m.node_count() - len(m.min_vertex_cover()))

    def test_independent_has_no_internal_edge(self):
        m = build([("l1", "r1"), ("l2", "r1"), ("l2", "r2")])
        inside = set(m.max_independent_set())
        for left, right in m.edges():
            self.assertFalse(left in inside and right in inside)


if __name__ == "__main__":
    unittest.main()
