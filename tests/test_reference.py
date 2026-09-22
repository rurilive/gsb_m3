"""reference 的行为基线：它是对拍的基准，规则不能变。"""

import unittest

from topoflow.graph import DiGraph
from topoflow.reference import (
    CycleError,
    order_problems,
    reference_is_acyclic,
    reference_order,
)


def build(edges, nodes=()):
    g = DiGraph()
    for node in nodes:
        g.add_node(node)
    for u, v in edges:
        g.add_edge(u, v)
    return g


class TestReferenceOrder(unittest.TestCase):
    def test_isolated_nodes_keep_arrival_order(self):
        self.assertEqual(reference_order(build([], nodes=("a", "b", "c"))), ["a", "b", "c"])

    def test_ties_go_to_earlier_node(self):
        # b 和 c 都随时可排，b 先登记，所以 b 先出队
        self.assertEqual(reference_order(build([("c", "a")], nodes=("a", "b", "c"))),
                         ["b", "c", "a"])

    def test_cycle_raises(self):
        with self.assertRaises(CycleError):
            reference_order(build([("a", "b"), ("b", "a")]))

    def test_self_loop_raises(self):
        with self.assertRaises(CycleError):
            reference_order(build([("a", "a")]))

    def test_is_acyclic(self):
        self.assertTrue(reference_is_acyclic(build([("a", "b")])))
        self.assertFalse(reference_is_acyclic(build([("a", "b"), ("b", "a")])))


class TestOrderProblems(unittest.TestCase):
    def test_clean_order_has_no_problems(self):
        self.assertEqual(order_problems(build([("a", "b"), ("a", "c")]), ["a", "b", "c"]), [])

    def test_missing_node_is_reported(self):
        problems = order_problems(build([("a", "b")]), ["a"])
        self.assertTrue(any("不在序里" in item for item in problems))

    def test_reversed_edge_is_reported(self):
        problems = order_problems(build([("a", "b")]), ["b", "a"])
        self.assertTrue(any("次序反了" in item for item in problems))

    def test_duplicate_node_is_reported(self):
        problems = order_problems(build([("a", "b")]), ["a", "a", "b"])
        self.assertTrue(any("多次" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
