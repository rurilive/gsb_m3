"""topocount 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import math
import unittest

from topocount.dag import (
    TopoCountError,
    InvalidGraphError,
    NodeNotFoundError,
    DAGCounter,
    brute_permutations,
)


def diamond():
    # 菱形依赖：0、1 都指向 2，2 再指向 3。
    return DAGCounter(4, [(0, 2), (1, 2), (2, 3)])


class TestBasics(unittest.TestCase):
    def test_counts(self):
        g = diamond()
        self.assertEqual(g.node_count(), 4)
        self.assertEqual(g.edge_count(), 3)

    def test_nodes_edges(self):
        g = diamond()
        self.assertEqual(g.nodes(), [0, 1, 2, 3])
        self.assertEqual(g.edges()[0], (0, 2))

    def test_in_degrees(self):
        self.assertEqual(diamond().in_degrees(), [0, 0, 2, 1])

    def test_successor_and_predecessor(self):
        g = diamond()
        self.assertEqual(g.successor_map()[0], [2])
        self.assertEqual(g.predecessor_map()[2], [0, 1])


class TestCountTopologicalOrders(unittest.TestCase):
    def test_empty_graph(self):
        self.assertEqual(DAGCounter(0, []).count_topological_orders(), 1)

    def test_single_node(self):
        self.assertEqual(DAGCounter(1, []).count_topological_orders(), 1)

    def test_no_edges(self):
        # 三个点彼此无约束，拓扑序是三的阶乘。
        self.assertEqual(DAGCounter(3, []).count_topological_orders(), math.factorial(3))

    def test_chain(self):
        g = DAGCounter(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(g.count_topological_orders(), 1)

    def test_diamond(self):
        self.assertEqual(diamond().count_topological_orders(), 2)

    def test_complete_dag(self):
        # 小到大的全序：拓扑序唯一。
        g = DAGCounter(3, [(0, 1), (0, 2), (1, 2)])
        self.assertEqual(g.count_topological_orders(), 1)

    def test_cycle_zero(self):
        g = DAGCounter(3, [(0, 1), (1, 2), (2, 0)])
        self.assertEqual(g.count_topological_orders(), 0)

    def test_self_loop_zero(self):
        self.assertEqual(DAGCounter(1, [(0, 0)]).count_topological_orders(), 0)

    def test_parallel_edges_same(self):
        # 平行边不改变序，个数与单边一致。
        self.assertEqual(DAGCounter(3, [(0, 1), (0, 1)]).count_topological_orders(), 3)


class TestOrders(unittest.TestCase):
    def test_topological_orders_sorted(self):
        self.assertEqual(diamond().topological_orders(), [[0, 1, 2, 3], [1, 0, 2, 3]])

    def test_min_order(self):
        self.assertEqual(diamond().min_topological_order(), [0, 1, 2, 3])

    def test_min_order_tie(self):
        # 0、1 都无入度，字典序最小的先取 0。
        g = DAGCounter(3, [(0, 2), (1, 2)])
        self.assertEqual(g.min_topological_order(), [0, 1, 2])

    def test_min_order_cycle_none(self):
        g = DAGCounter(2, [(0, 1), (1, 0)])
        self.assertIsNone(g.min_topological_order())

    def test_has_order(self):
        self.assertTrue(diamond().has_topological_order())
        self.assertFalse(DAGCounter(2, [(0, 1), (1, 0)]).has_topological_order())

    def test_repeat_run_equal(self):
        g = diamond()
        self.assertEqual(g.topological_orders(), g.topological_orders())


class TestWeightAndRanges(unittest.TestCase):
    def test_max_weight_order(self):
        g = diamond()
        total, order = g.max_weight_order([3, 1, 2, 4])
        self.assertEqual(total, 10)
        self.assertEqual(order, [0, 1, 2, 3])

    def test_max_weight_order_as_dict(self):
        g = DAGCounter(3, [(0, 1), (0, 2)])
        total, order = g.max_weight_order({0: 1, 1: 2, 2: 3})
        self.assertEqual(total, 6)
        self.assertEqual(order[0], 0)

    def test_max_weight_cycle_none(self):
        g = DAGCounter(2, [(0, 1), (1, 0)])
        self.assertIsNone(g.max_weight_order([1, 1]))

    def test_position_ranges(self):
        # 0、1 只争第一位，2 恒在第三位，3 恒在末位。
        self.assertEqual(diamond().position_ranges(), [(0, 1), (0, 1), (2, 2), (3, 3)])

    def test_position_ranges_cycle_none(self):
        g = DAGCounter(2, [(0, 1), (1, 0)])
        self.assertIsNone(g.position_ranges())


class TestCostModel(unittest.TestCase):
    def test_brute_permutations_small(self):
        # 三个点，六种排列，全检查。
        self.assertEqual(brute_permutations(3, []), [6, 0])

    def test_brute_permutations_factorial(self):
        self.assertEqual(brute_permutations(4, [])[0], math.factorial(4))

    def test_brute_permutations_break(self):
        # 边一多就提前中断，边检查次数低于每个排列把每条边都检查一遍的满额。
        edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        visits, checks = brute_permutations(4, edges)
        self.assertEqual(visits, math.factorial(4))
        self.assertLess(checks, visits * len(edges))

    def test_counters_nonzero(self):
        g = diamond()
        g.reset_counters()
        g.count_topological_orders()
        c = g.counters()
        self.assertGreater(c["perm_visits"], 0)
        self.assertGreater(c["edge_checks"], 0)

    def test_counters_reset(self):
        g = diamond()
        g.count_topological_orders()
        g.reset_counters()
        self.assertEqual(g.counters(), {"perm_visits": 0, "edge_checks": 0})


class TestErrors(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(InvalidGraphError, TopoCountError))
        self.assertTrue(issubclass(NodeNotFoundError, TopoCountError))

    def test_negative_nodes_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DAGCounter(-1, [])

    def test_non_list_edges_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DAGCounter(3, "abc")

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DAGCounter(3, [(0, 1, 2)])

    def test_endpoint_out_of_range(self):
        with self.assertRaises(InvalidGraphError):
            DAGCounter(3, [(0, 9)])

    def test_bad_weight(self):
        with self.assertRaises(InvalidGraphError):
            diamond().max_weight_order([1, 1, "x", 1])

    def test_weight_length_mismatch(self):
        with self.assertRaises(InvalidGraphError):
            diamond().max_weight_order([1, 1, 1])

    def test_unknown_node(self):
        with self.assertRaises(NodeNotFoundError):
            diamond()._require_node(99)


if __name__ == "__main__":
    unittest.main()
