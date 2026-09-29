"""基线测试：锁住改造前 mcfx.flow.FlatMcf 的现状行为。

这些断言描述的是"当前朴素实现的事实"，不是"最终应当的样子"：
  - max_flow 只保证流量最优，费用不保证最优；
  - path_cost 只给单条最短路的费用，是粗略参考；
  - has_feasible 只按可达流量判断可行性。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcfx.flow import (  # noqa: E402
    FlatMcf,
    McfError,
    CapacityError,
    NodeError,
)


def build_diamond():
    """一张经典菱形图：s 有两条到 t 的路径，各段费用不同。

        s -> a  容量 3  费用 1
        s -> b  容量 3  费用 2
        a -> t  容量 3  费用 1
        b -> t  容量 3  费用 5
    """
    g = FlatMcf()
    g.add_edge("s", "a", 3, 1)
    g.add_edge("s", "b", 3, 2)
    g.add_edge("a", "t", 3, 1)
    g.add_edge("b", "t", 3, 5)
    return g


class TestGraphConstruction(unittest.TestCase):
    def test_add_edge_registers_nodes(self):
        g = FlatMcf()
        g.add_edge("s", "t", 5, 0)
        self.assertEqual(g.nodes(), ["s", "t"])

    def test_add_node_isolated(self):
        g = FlatMcf()
        g.add_node("z")
        g.add_edge("s", "t", 1, 0)
        self.assertEqual(g.nodes(), ["s", "t", "z"])

    def test_parallel_edges_are_independent(self):
        g = FlatMcf()
        g.add_edge("s", "t", 2, 1)
        g.add_edge("s", "t", 3, 9)
        self.assertEqual(len(g.adj["s"]), 2)

    def test_negative_capacity_raises(self):
        g = FlatMcf()
        with self.assertRaises(CapacityError):
            g.add_edge("s", "t", -1, 0)

    def test_non_numeric_capacity_raises(self):
        g = FlatMcf()
        with self.assertRaises(CapacityError):
            g.add_edge("s", "t", "big", 0)

    def test_empty_node_name_raises(self):
        g = FlatMcf()
        with self.assertRaises(NodeError):
            g.add_node("")


class TestMaxFlow(unittest.TestCase):
    def test_simple_path(self):
        g = FlatMcf()
        g.add_edge("s", "t", 4, 3)
        flow, _ = g.max_flow("s", "t")
        self.assertEqual(flow, 4)

    def test_bottleneck(self):
        g = FlatMcf()
        g.add_edge("s", "a", 5, 0)
        g.add_edge("a", "t", 2, 0)
        flow, _ = g.max_flow("s", "t")
        self.assertEqual(flow, 2)

    def test_diamond_max_flow_is_six(self):
        g = build_diamond()
        flow, _ = g.max_flow("s", "t")
        self.assertEqual(flow, 6)

    def test_no_path_gives_zero(self):
        g = FlatMcf()
        g.add_edge("s", "a", 3, 0)
        g.add_edge("b", "t", 3, 0)
        flow, _ = g.max_flow("s", "t")
        self.assertEqual(flow, 0)

    def test_source_equals_sink_zero(self):
        g = build_diamond()
        flow, cost = g.max_flow("s", "s")
        self.assertEqual(flow, 0)
        self.assertEqual(cost, 0)

    def test_unknown_node_raises(self):
        g = build_diamond()
        with self.assertRaises(NodeError):
            g.max_flow("s", "nope")

    def test_isolated_node_has_no_flow(self):
        g = FlatMcf()
        g.add_edge("s", "t", 1, 0)
        g.add_node("iso")
        flow, _ = g.max_flow("s", "iso")
        self.assertEqual(flow, 0)

    def test_zero_capacity_edge_ignored(self):
        g = FlatMcf()
        g.add_edge("s", "t", 0, 0)
        flow, _ = g.max_flow("s", "t")
        self.assertEqual(flow, 0)

    def test_repeated_runs_agree(self):
        g1 = build_diamond()
        g2 = build_diamond()
        self.assertEqual(g1.max_flow("s", "t"), g2.max_flow("s", "t"))


class TestPathCost(unittest.TestCase):
    def test_single_edge_cost(self):
        g = FlatMcf()
        g.add_edge("s", "t", 2, 7)
        self.assertEqual(g.path_cost("s", "t"), 7)

    def test_picks_cheaper_branch(self):
        # 朴素最短路会走 s->a->t，费用 1+1=2，而不是 s->b->t 的 2+5=7
        g = build_diamond()
        self.assertEqual(g.path_cost("s", "t"), 2)

    def test_no_path_returns_none(self):
        g = FlatMcf()
        g.add_edge("s", "a", 1, 1)
        g.add_node("t")
        self.assertIsNone(g.path_cost("s", "t"))

    def test_source_equals_sink_zero(self):
        g = build_diamond()
        self.assertEqual(g.path_cost("s", "s"), 0)

    def test_zero_capacity_hides_path(self):
        g = FlatMcf()
        g.add_edge("s", "t", 0, 1)
        self.assertIsNone(g.path_cost("s", "t"))


class TestHasFeasible(unittest.TestCase):
    def test_need_within_capacity(self):
        g = build_diamond()
        self.assertTrue(g.has_feasible("s", "t", 6))

    def test_need_above_capacity(self):
        g = build_diamond()
        self.assertFalse(g.has_feasible("s", "t", 7))

    def test_need_zero_always_true(self):
        g = build_diamond()
        self.assertTrue(g.has_feasible("s", "t", 0))

    def test_negative_need_raises(self):
        g = build_diamond()
        with self.assertRaises(CapacityError):
            g.has_feasible("s", "t", -1)


class TestErrorHierarchy(unittest.TestCase):
    def test_capacity_error_is_mcf_error(self):
        self.assertTrue(issubclass(CapacityError, McfError))

    def test_node_error_is_mcf_error(self):
        self.assertTrue(issubclass(NodeError, McfError))


if __name__ == "__main__":
    unittest.main()
