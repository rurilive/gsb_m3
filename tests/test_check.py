"""基线测试：锁定 DagCheck 的成环检查行为。

这些断言在改造前后都必须成立，改造时不得修改本文件。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dagwer import DagCheck


class TestDagCheckBaseline(unittest.TestCase):

    def test_empty_edges_no_cycle(self):
        self.assertFalse(DagCheck([]).has_cycle())

    def test_single_edge_no_cycle(self):
        self.assertFalse(DagCheck([("a", "b")]).has_cycle())

    def test_chain_no_cycle(self):
        self.assertFalse(DagCheck([("a", "b"), ("b", "c"), ("c", "d")]).has_cycle())

    def test_simple_cycle(self):
        self.assertTrue(DagCheck([("a", "b"), ("b", "c"), ("c", "a")]).has_cycle())

    def test_self_loop_is_cycle(self):
        self.assertTrue(DagCheck([("a", "a")]).has_cycle())

    def test_two_disjoint_components_one_cyclic(self):
        edges = [("a", "b"), ("c", "d"), ("d", "e"), ("e", "c")]
        self.assertTrue(DagCheck(edges).has_cycle())

    def test_add_edge_then_check(self):
        check = DagCheck()
        check.add_edge("a", "b")
        check.add_edge("b", "c")
        self.assertFalse(check.has_cycle())
        check.add_edge("c", "a")
        self.assertTrue(check.has_cycle())

    def test_edges_property_is_copy(self):
        check = DagCheck([("a", "b")])
        snapshot = check.edges
        snapshot.append(("x", "y"))
        self.assertEqual(check.edges, [("a", "b")])


if __name__ == "__main__":
    unittest.main()
