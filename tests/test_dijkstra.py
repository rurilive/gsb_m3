"""基线测试：锁住改造前 shortestpath.dijkstra.NaiveGraph 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - 每轮在未确定结点里线性扫描找出距离最小者，再逐边松驰其邻居；
  - 找最小这一步整体线性，结点数为 n 的连通图比较次数为 n 乘 n 加一 除以 二；
  - 路径由前驱逐段回溯拼出，首项为源点，不可达点不出现在结果里；
  - 不可达点用「距离表里取不到该键」这一口径表示；
  - 平行边取最小权，自环不参与松驰，权为零的边照常参与，孤点可显式登记；
  - 源点或终点不在图中、出现负权边，分别抛对应异常且都继承基类；
  - 同一个实例反复调用不残留痕迹，固定输入重复跑结果一致。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shortestpath.dijkstra import (  # noqa: E402
    NaiveGraph,
    NegativeWeightError,
    NodeNotFoundError,
    ShortestPathError,
    UnreachableNodeError,
)


def small_graph():
    """四结点连通图：A 到 B、C、D 的确定最短距离依次是 1、2、3。"""
    return NaiveGraph([
        ("A", "B", 1),
        ("A", "C", 4),
        ("B", "C", 1),
        ("B", "D", 5),
        ("C", "D", 1),
    ])


class TestBaselineDistances(unittest.TestCase):
    def setUp(self):
        self.g = small_graph()

    def test_shortest_distances(self):
        self.assertEqual(self.g.distances("A"),
                         {"A": 0, "B": 1, "C": 2, "D": 3})

    def test_source_itself_is_zero(self):
        self.assertEqual(self.g.distances("A")["A"], 0)

    def test_distances_is_a_copy(self):
        got = self.g.distances("A")
        got["A"] = 999
        self.assertEqual(self.g.distances("A")["A"], 0)

    def test_nodes_keep_first_seen_order(self):
        self.assertEqual(self.g.nodes(), ["A", "B", "C", "D"])
        self.assertEqual(self.g.size(), 4)


class TestBaselinePaths(unittest.TestCase):
    def setUp(self):
        self.g = small_graph()

    def test_paths_are_rebuilt_from_predecessors(self):
        got = self.g.paths("A")
        self.assertEqual(got["A"], ["A"])
        self.assertEqual(got["B"], ["A", "B"])
        self.assertEqual(got["C"], ["A", "B", "C"])
        self.assertEqual(got["D"], ["A", "B", "C", "D"])

    def test_paths_match_distances_lengths(self):
        # 路径逐段累加的权重要与距离逐项一致
        g = NaiveGraph([("A", "B", 2), ("B", "C", 3), ("A", "C", 9)])
        weights = {"A|B": 2, "B|C": 3}
        dist = g.distances("A")
        for node, route in g.paths("A").items():
            total = 0
            for u, v in zip(route, route[1:]):
                total += weights["%s|%s" % (u, v)]
            self.assertEqual(total, dist[node])

    def test_path_helper(self):
        self.assertEqual(self.g.path("A", "D"), ["A", "B", "C", "D"])

    def test_same_source_and_target(self):
        self.assertEqual(self.g.path("A", "A"), ["A"])

    def test_paths_is_a_copy(self):
        got = self.g.paths("A")
        got["B"].append("X")
        self.assertEqual(self.g.paths("A")["B"], ["A", "B"])


class TestBaselineLinearMinSearch(unittest.TestCase):
    def test_lookup_count_is_quadratic(self):
        # 四结点连通图：每轮找最小扫过 4、3、2、1 个候选，合计 10
        self.assertEqual(small_graph().lookups("A"), 10)

    def test_lookup_count_grows_with_nodes(self):
        chain = NaiveGraph([(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 4, 1)])
        # 五结点链：5 加 4 加 3 加 2 加 1
        self.assertEqual(chain.lookups(0), 15)

    def test_repeated_query_recomputes(self):
        g = small_graph()
        first = g.lookups("A")
        second = g.lookups("A")
        self.assertEqual(first, second)

    def test_stats_reports_counts(self):
        st = small_graph().stats("A")
        self.assertEqual(st["nodes"], 4)
        self.assertEqual(st["edges"], 5)
        self.assertEqual(st["reachable"], 4)
        self.assertEqual(st["lookups"], 10)

    def test_stats_is_fresh_dict(self):
        g = small_graph()
        st = g.stats("A")
        st["nodes"] = 999
        self.assertEqual(g.stats("A")["nodes"], 4)


class TestBaselineEdges(unittest.TestCase):
    def test_parallel_edges_keep_minimum(self):
        g = NaiveGraph([("X", "Y", 5), ("X", "Y", 2), ("X", "Y", 7)])
        self.assertEqual(g.distances("X"), {"X": 0, "Y": 2})
        self.assertEqual(g.stats("X")["edges"], 1)

    def test_self_loop_is_ignored(self):
        g = NaiveGraph([("S", "S", 7), ("S", "T", 3)])
        self.assertEqual(g.distances("S"), {"S": 0, "T": 3})

    def test_zero_weight_edge(self):
        g = NaiveGraph([("P", "Q", 0)])
        self.assertEqual(g.distances("P"), {"P": 0, "Q": 0})
        self.assertEqual(g.path("P", "Q"), ["P", "Q"])

    def test_isolated_node_is_unreachable(self):
        g = NaiveGraph([("A", "B", 1)])
        g.add_node("Z")
        self.assertNotIn("Z", g.distances("A"))
        self.assertEqual(g.unreachable("A"), ["Z"])
        with self.assertRaises(UnreachableNodeError):
            g.path("A", "Z")

    def test_disconnected_components(self):
        g = NaiveGraph([("A", "B", 1), ("C", "D", 1)])
        self.assertEqual(g.distances("A"), {"A": 0, "B": 1})
        self.assertEqual(g.unreachable("A"), ["C", "D"])
        self.assertNotIn("C", g.paths("A"))

    def test_empty_graph_has_no_edges(self):
        g = NaiveGraph([])
        g.add_node("Lone")
        self.assertEqual(g.size(), 1)
        self.assertEqual(g.distances("Lone"), {"Lone": 0})


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (NegativeWeightError, NodeNotFoundError,
                    UnreachableNodeError):
            self.assertTrue(issubclass(exc, ShortestPathError))

    def test_negative_weight_rejected(self):
        with self.assertRaises(NegativeWeightError):
            NaiveGraph([("A", "B", -1)])

    def test_non_numeric_weight_rejected(self):
        with self.assertRaises(NegativeWeightError):
            NaiveGraph([("A", "B", "x")])

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(ShortestPathError):
            NaiveGraph([("A", "B")])

    def test_none_edges_rejected(self):
        with self.assertRaises(ShortestPathError):
            NaiveGraph(None)

    def test_unknown_source_rejected(self):
        g = NaiveGraph([("A", "B", 1)])
        with self.assertRaises(NodeNotFoundError):
            g.distances("NOPE")
        with self.assertRaises(NodeNotFoundError):
            g.unreachable("NOPE")

    def test_unknown_target_rejected(self):
        g = NaiveGraph([("A", "B", 1)])
        with self.assertRaises(NodeNotFoundError):
            g.path("A", "NOPE")


class TestBaselineDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        def run():
            g = small_graph()
            return (g.distances("A"), g.paths("A"), g.unreachable("A"),
                    g.lookups("A"), g.stats("A"))

        self.assertEqual(run(), run())

    def test_no_cross_call_residue(self):
        g = small_graph()
        first = g.distances("A")
        second = g.distances("A")
        self.assertEqual(first, second)
        self.assertEqual(g.lookups("A"), g.lookups("A"))


if __name__ == "__main__":
    unittest.main()
