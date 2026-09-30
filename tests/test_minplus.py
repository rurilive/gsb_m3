"""基线测试：锁住改造前 minplus.minplus 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - shortest_paths 做恰好若干步的最短路，每推进一步把整张表重扫一遍做重复松弛；
  - step_transitions 按边逐项枚举取最小加，推一步整条向量重扫一遍；
  - matrix_power 把同一个最小加矩阵连乘指数那么多遍；
  - mat_mul 做一次最小加矩阵乘法。

改造时本文件一字不得修改，且必须保持全绿。
"""

import math
import unittest

from minplus.minplus import (
    INF,
    MatPlusKit,
    MatrixErro,
    MinPlusErro,
    PatternErro,
    mat_mul,
    matrix_power,
    shortest_paths,
    step_transitions,
)


# 三角图，含一条零权边与一条捷径。
TRI_NODES = ["s", "a", "b"]
TRI_EDGES = [("s", "a", 2.0), ("a", "b", 3.0), ("s", "b", 10.0), ("b", "a", 0.0)]


def as_lists(matrix):
    return [list(row) for row in matrix]


class TestShortestPathsBaseline(unittest.TestCase):
    def test_zero_steps_is_identity(self):
        matrix, order = shortest_paths(TRI_NODES, TRI_EDGES, 0)
        self.assertEqual(order, ["s", "a", "b"])
        self.assertEqual(as_lists(matrix), [[0.0, INF, INF],
                                            [INF, 0.0, INF],
                                            [INF, INF, 0.0]])

    def test_one_step_uses_zero_weight_edge(self):
        matrix, _ = shortest_paths(TRI_NODES, TRI_EDGES, 1)
        self.assertEqual(matrix[0][1], 2.0)
        self.assertEqual(matrix[1][2], 3.0)
        self.assertEqual(matrix[0][2], 10.0)
        self.assertEqual(matrix[2][1], 0.0)

    def test_two_steps_finds_cheaper_route(self):
        # s 走两步到 b：s->a->b 是 5，比 s->b 的直连 10 更短。
        matrix, _ = shortest_paths(TRI_NODES, TRI_EDGES, 2)
        self.assertEqual(matrix[0][2], 5.0)

    def test_unreachable_stays_infinite(self):
        matrix, _ = shortest_paths(TRI_NODES, TRI_EDGES, 3)
        self.assertTrue(math.isinf(matrix[1][0]))
        self.assertTrue(math.isinf(matrix[2][2]))

    def test_self_loop_across_step_counts(self):
        nodes = ["x", "y"]
        edges = [("x", "y", 2.0), ("y", "y", 1.0)]
        m1, _ = shortest_paths(nodes, edges, 1)
        self.assertEqual(m1[1][1], 1.0)
        m2, _ = shortest_paths(nodes, edges, 2)
        self.assertEqual(m2[1][1], 2.0)

    def test_empty_graph(self):
        matrix, order = shortest_paths([], [], 5)
        self.assertEqual(matrix, [])
        self.assertEqual(order, [])

    def test_negative_steps_raises(self):
        with self.assertRaises(PatternErro):
            shortest_paths(TRI_NODES, TRI_EDGES, -1)

    def test_non_integer_steps_raises(self):
        with self.assertRaises(PatternErro):
            shortest_paths(TRI_NODES, TRI_EDGES, 1.5)

    def test_bad_edge_raises(self):
        with self.assertRaises(MatrixErro):
            shortest_paths(["a"], [("a", "b")], 1)


class TestStepTransitionsBaseline(unittest.TestCase):
    def test_zero_steps_returns_init(self):
        vec, order = step_transitions([0.0, INF, INF], TRI_NODES, TRI_EDGES, 0)
        self.assertEqual(order, ["s", "a", "b"])
        self.assertEqual(vec, [0.0, INF, INF])

    def test_two_steps_shortest_reach(self):
        vec, _ = step_transitions([0.0, INF, INF], TRI_NODES, TRI_EDGES, 2)
        self.assertEqual(vec[2], 5.0)
        self.assertEqual(vec[1], 10.0)

    def test_unreachable_is_inf(self):
        vec, _ = step_transitions([INF, 0.0, INF], TRI_NODES, TRI_EDGES, 1)
        self.assertEqual(vec[2], 3.0)
        self.assertTrue(math.isinf(vec[0]))

    def test_length_mismatch_raises(self):
        with self.assertRaises(MatrixErro):
            step_transitions([0.0], TRI_NODES, TRI_EDGES, 1)

    def test_negative_steps_raises(self):
        with self.assertRaises(PatternErro):
            step_transitions([0.0, 0.0, 0.0], TRI_NODES, TRI_EDGES, -1)


class TestMatrixPowerBaseline(unittest.TestCase):
    BASE = [[0.0, 1.0, INF], [INF, 0.0, 2.0], [4.0, INF, 0.0]]
    EYE = [[0.0, INF, INF], [INF, 0.0, INF], [INF, INF, 0.0]]

    def test_power_zero_is_identity(self):
        self.assertEqual(as_lists(matrix_power(self.BASE, 0)), self.EYE)

    def test_power_one_is_self(self):
        self.assertEqual(as_lists(matrix_power(self.BASE, 1)), self.BASE)

    def test_power_two(self):
        # 最小加平方等于自己做一次最小加矩阵乘法。
        self.assertEqual(as_lists(matrix_power(self.BASE, 2)),
                         as_lists(mat_mul(self.BASE, self.BASE)))

    def test_mat_mul_min_plus_semantics(self):
        a = [[0.0, 5.0], [INF, 0.0]]
        b = [[0.0, INF], [2.0, 0.0]]
        self.assertEqual(as_lists(mat_mul(a, b)), [[0.0, 5.0], [2.0, 0.0]])

    def test_mat_mul_shape_mismatch_raises(self):
        with self.assertRaises(MatrixErro):
            mat_mul([[0.0, 1.0, 2.0]], [[0.0, 1.0]])

    def test_non_square_power_raises(self):
        with self.assertRaises(MatrixErro):
            matrix_power([[0.0, 1.0]], 2)

    def test_negative_exponent_raises(self):
        with self.assertRaises(PatternErro):
            matrix_power(self.BASE, -1)


class TestKitCountersBaseline(unittest.TestCase):
    def setUp(self):
        self.kit = MatPlusKit()

    def test_iter_steps_match_steps(self):
        self.kit.shortest_paths(TRI_NODES, TRI_EDGES, 4)
        self.assertEqual(self.kit.iter_steps, 4)

    def test_trans_steps_match_steps(self):
        self.kit.step_transitions([0.0, INF, INF], TRI_NODES, TRI_EDGES, 3)
        self.assertEqual(self.kit.trans_steps, 3)

    def test_mult_count_match_exponent(self):
        self.kit.matrix_power([[0.0, 1.0], [1.0, 0.0]], 5)
        self.assertEqual(self.kit.mult_count, 5)

    def test_counters_reset_between_calls(self):
        self.kit.shortest_paths(TRI_NODES, TRI_EDGES, 4)
        first = self.kit.iter_steps
        self.kit.shortest_paths(TRI_NODES, TRI_EDGES, 4)
        self.assertEqual(self.kit.iter_steps, first)

    def test_kit_matches_functions(self):
        kit_matrix, _ = self.kit.shortest_paths(TRI_NODES, TRI_EDGES, 3)
        plain_matrix, _ = shortest_paths(TRI_NODES, TRI_EDGES, 3)
        self.assertEqual(as_lists(kit_matrix), as_lists(plain_matrix))


class TestErroHierarchyBaseline(unittest.TestCase):
    def test_matrix_erro_is_minplus_erro(self):
        self.assertTrue(issubclass(MatrixErro, MinPlusErro))

    def test_pattern_erro_is_minplus_erro(self):
        self.assertTrue(issubclass(PatternErro, MinPlusErro))

    def test_minplus_erro_is_exception(self):
        self.assertTrue(issubclass(MinPlusErro, Exception))


if __name__ == "__main__":
    unittest.main()
