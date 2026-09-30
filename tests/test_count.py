"""基线测试：锁住改造前 pathcount 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - count_walks_exact 从起点逐层深度搜索，把每条走法整条枚举出来再计数；
  - count_paths_between 靠深度搜索枚举简单路径，走过的点不重复；
  - count_walks_up_to 对长度零到上界各枚举一遍再累加；
  - has_cycle_of_length 与 shortest_cycle 按长度从小到大枚举判定；
  - mat_mul 三重循环、mat_pow 逐次相乘，都是立方乃至指数量级。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathcount.count import (  # noqa: E402
    DirectedGraph,
    GraphErro,
    PathCounter,
    PathErro,
    WalkerErro,
    mat_mul,
    mat_pow,
)


def diamond():
    """菱形图：零到一、零到二、一到三、二到三，四条边。"""
    return DirectedGraph(nodes=[0, 1, 2, 3],
                         edges=[(0, 1), (0, 2), (1, 3), (2, 3)])


def chain():
    """链式图：零到一、一到二、二到三，一条路的走法唯一。"""
    return DirectedGraph(nodes=[0, 1, 2, 3],
                         edges=[(0, 1), (1, 2), (2, 3)])


class TestGraphBaseline(unittest.TestCase):
    def test_nodes_in_order(self):
        g = diamond()
        self.assertEqual(g.nodes(), [0, 1, 2, 3])

    def test_self_loop_allowed(self):
        g = DirectedGraph(nodes=[0, 1], edges=[(0, 0), (0, 1)])
        self.assertTrue(g.has_edge(0, 0))
        self.assertEqual(g.edge_count(0, 0), 1)

    def test_duplicate_node_raises(self):
        with self.assertRaises(GraphErro):
            DirectedGraph(nodes=[0, 1, 1], edges=[])

    def test_edge_endpoint_out_of_graph_raises(self):
        with self.assertRaises(GraphErro):
            DirectedGraph(nodes=[0, 1], edges=[(0, 2)])

    def test_non_int_node_raises(self):
        with self.assertRaises(GraphErro):
            DirectedGraph(nodes=[0, "a"], edges=[])

    def test_adjacency_matrix(self):
        self.assertEqual(diamond().adjacency_matrix(),
                         [[0, 1, 1, 0],
                          [0, 0, 0, 1],
                          [0, 0, 0, 1],
                          [0, 0, 0, 0]])

    def test_out_neighbors_sorted(self):
        g = DirectedGraph(nodes=[0, 1, 2], edges=[(0, 2), (0, 1)])
        self.assertEqual(g.out_neighbors(0), [1, 2])

    def test_edges_sorted(self):
        self.assertEqual(diamond().edges(),
                         [(0, 1), (0, 2), (1, 3), (2, 3)])

    def test_unknown_node_raises(self):
        with self.assertRaises(WalkerErro):
            diamond().out_neighbors(9)


class TestWalkExactBaseline(unittest.TestCase):
    def setUp(self):
        self.g = diamond()
        self.c = PathCounter(self.g)

    def test_zero_steps_same_node(self):
        self.assertEqual(self.c.count_walks_exact(0, 0, 0), 1)

    def test_zero_steps_different_node(self):
        self.assertEqual(self.c.count_walks_exact(0, 3, 0), 0)

    def test_one_step_follows_edge(self):
        self.assertEqual(self.c.count_walks_exact(0, 1, 1), 1)
        self.assertEqual(self.c.count_walks_exact(0, 3, 1), 0)

    def test_two_steps_two_routes(self):
        self.assertEqual(self.c.count_walks_exact(0, 3, 2), 2)

    def test_repeated_nodes_allowed(self):
        g = DirectedGraph(nodes=[0, 1], edges=[(0, 1), (1, 0), (1, 1)])
        c = PathCounter(g)
        # 长度三落到一的走法有两条：零到一到零到一，零到一到一到一。
        self.assertEqual(c.count_walks_exact(0, 1, 3), 2)

    def test_unreachable_is_zero(self):
        self.assertEqual(self.c.count_walks_exact(3, 0, 4), 0)

    def test_negative_steps_raises(self):
        with self.assertRaises(WalkerErro):
            self.c.count_walks_exact(0, 3, -1)

    def test_depth_steps_positive(self):
        self.c.count_walks_exact(0, 3, 4)
        self.assertGreater(self.c.depth_steps, 0)

    def test_enum_paths_recorded(self):
        self.c.count_walks_exact(0, 3, 2)
        self.assertGreater(self.c.enum_paths, 0)


class TestPathsBetweenBaseline(unittest.TestCase):
    def setUp(self):
        self.c = PathCounter(diamond())

    def test_same_node_is_one(self):
        self.assertEqual(self.c.count_paths_between(0, 0), 1)

    def test_diamond_has_two_simple_paths(self):
        self.assertEqual(self.c.count_paths_between(0, 3), 2)

    def test_chain_has_one(self):
        self.assertEqual(PathCounter(chain()).count_paths_between(0, 3), 1)

    def test_no_reverse_route(self):
        self.assertEqual(self.c.count_paths_between(3, 0), 0)

    def test_cycle_still_simple(self):
        g = DirectedGraph(nodes=[0, 1], edges=[(0, 1), (1, 0)])
        self.assertEqual(PathCounter(g).count_paths_between(0, 1), 1)

    def test_unknown_node_raises(self):
        with self.assertRaises(WalkerErro):
            self.c.count_paths_between(0, 9)


class TestWalkUpToBaseline(unittest.TestCase):
    def setUp(self):
        self.c = PathCounter(diamond())

    def test_bound_zero(self):
        self.assertEqual(self.c.count_walks_up_to(0, 0, 0), 1)

    def test_bound_two_matches_enumeration(self):
        self.assertEqual(self.c.count_walks_up_to(0, 3, 2), 2)

    def test_bound_accumulates_each_length(self):
        # 带自环的图上，长度一到三各有一条落到一的走法，累计得三。
        g = DirectedGraph(nodes=[0, 1], edges=[(0, 1), (1, 1)])
        c = PathCounter(g)
        self.assertEqual(c.count_walks_up_to(0, 1, 3), 3)

    def test_negative_bound_raises(self):
        with self.assertRaises(WalkerErro):
            self.c.count_walks_up_to(0, 3, -1)


class TestCycleBaseline(unittest.TestCase):
    def test_no_cycle_diamond(self):
        c = PathCounter(diamond())
        self.assertFalse(c.has_cycle_of_length(3))
        self.assertIsNone(c.shortest_cycle())

    def test_self_loop_is_length_one(self):
        g = DirectedGraph(nodes=[0, 1], edges=[(0, 1), (0, 0)])
        c = PathCounter(g)
        self.assertTrue(c.has_cycle_of_length(1))
        self.assertEqual(c.shortest_cycle(), 1)

    def test_triangle_cycle(self):
        g = DirectedGraph(nodes=[0, 1, 2],
                          edges=[(0, 1), (1, 2), (2, 0)])
        c = PathCounter(g)
        self.assertTrue(c.has_cycle_of_length(3))
        self.assertFalse(c.has_cycle_of_length(2))
        self.assertEqual(c.shortest_cycle(), 3)

    def test_nonpositive_length_raises(self):
        with self.assertRaises(WalkerErro):
            PathCounter(diamond()).has_cycle_of_length(0)


class TestMatrixBaseline(unittest.TestCase):
    A = [[0, 1, 1, 0],
         [0, 0, 0, 1],
         [0, 0, 0, 1],
         [0, 0, 0, 0]]

    def test_mat_mul_square(self):
        self.assertEqual(mat_mul(self.A, self.A, 10),
                         [[0, 0, 0, 2],
                          [0, 0, 0, 0],
                          [0, 0, 0, 0],
                          [0, 0, 0, 0]])

    def test_mat_pow_zero_identity(self):
        self.assertEqual(mat_pow(self.A, 0, 10),
                         [[1, 0, 0, 0], [0, 1, 0, 0],
                          [0, 0, 1, 0], [0, 0, 0, 1]])

    def test_mat_pow_two_counts_routes(self):
        self.assertEqual(mat_pow(self.A, 2, 10),
                         [[0, 0, 0, 2],
                          [0, 0, 0, 0],
                          [0, 0, 0, 0],
                          [0, 0, 0, 0]])

    def test_mat_mul_mod_applied(self):
        self.assertEqual(mat_mul([[2, 2]], [[2], [2]], 3), [[2]])

    def test_mat_pow_mult_count_is_exponent(self):
        c = PathCounter(diamond())
        c.mat_pow(self.A, 5, 10)
        self.assertEqual(c.mult_count, 5)

    def test_shape_mismatch_raises(self):
        with self.assertRaises(WalkerErro):
            mat_mul([[1, 2, 3]], [[1, 2]], 10)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        c1 = PathCounter(diamond())
        c2 = PathCounter(diamond())
        self.assertEqual(c1.count_walks_exact(0, 3, 6),
                         c2.count_walks_exact(0, 3, 6))
        self.assertEqual(c1.count_paths_between(0, 3),
                         c2.count_paths_between(0, 3))

    def test_counters_reset_between_calls(self):
        c = PathCounter(diamond())
        c.count_walks_exact(0, 3, 4)
        first = c.depth_steps
        c.count_walks_exact(0, 3, 4)
        self.assertEqual(c.depth_steps, first)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(GraphErro, PathErro))
        self.assertTrue(issubclass(WalkerErro, PathErro))
        self.assertTrue(issubclass(PathErro, Exception))


if __name__ == "__main__":
    unittest.main()
