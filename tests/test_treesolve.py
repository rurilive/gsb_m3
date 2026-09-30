"""朴素树求解器的基线行为测试。

锁住改造前的现状: 加边与邻居查询的口径, 枚举选法求出的最大独立集与最小点
覆盖的大小与并列取用口径, 独立集与点覆盖的判定, 以及异常基类与非法入参的
拒绝。本文件在改造后一字不许改, 且必须一直全绿。
"""

import unittest

from treeindset import (
    Erro,
    Solution,
    TreeInputError,
    TreeSolve,
    UnknownVertexError,
)


def build(n, pairs):
    """建一棵 n 个顶点的树, 按 pairs 里的 (u, v) 加边。"""
    t = TreeSolve(n)
    for u, v in pairs:
        t.add_edge(u, v)
    return t


PATH4 = [(0, 1), (1, 2), (2, 3)]
STAR4 = [(0, 1), (0, 2), (0, 3)]
PAW4 = [(0, 1), (1, 2), (2, 0), (2, 3)]


class TestStructure(unittest.TestCase):
    def test_empty_tree(self):
        t = TreeSolve(0)
        self.assertEqual(t.n, 0)
        self.assertEqual(t.edges(), [])
        self.assertEqual(t.edge_count(), 0)
        self.assertEqual(t.max_independent_set().size, 0)
        self.assertEqual(t.min_vertex_cover().size, 0)

    def test_single_vertex(self):
        t = TreeSolve(1)
        self.assertEqual(t.max_independent_set(), Solution([0]))
        self.assertEqual(t.min_vertex_cover(), Solution([]))

    def test_add_edge_and_neighbors(self):
        t = build(4, PATH4)
        self.assertEqual(t.edge_count(), 3)
        self.assertEqual(t.edges(), [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(t.neighbors(1), [0, 2])
        self.assertEqual(t.neighbors(0), [1])

    def test_duplicate_edge_is_idempotent(self):
        t = build(2, [(0, 1), (1, 0), (0, 1)])
        self.assertEqual(t.edge_count(), 1)
        self.assertEqual(t.edges(), [(0, 1)])

    def test_neighbors_are_sorted_and_deduped(self):
        t = TreeSolve(3)
        t.add_edge(0, 1)
        t.add_edge(0, 2)
        t.add_edge(1, 0)
        self.assertEqual(t.neighbors(0), [1, 2])

    def test_solution_keeps_sorted_vertices(self):
        s = Solution([3, 1, 2, 1])
        self.assertEqual(s.vertices, (1, 2, 3))
        self.assertEqual(s.size, 3)


class TestResults(unittest.TestCase):
    def test_path4(self):
        t = build(4, PATH4)
        self.assertEqual(t.max_independent_set(), Solution([0, 2]))
        self.assertEqual(t.max_independent_set().size, 2)
        self.assertEqual(t.min_vertex_cover(), Solution([0, 2]))
        self.assertEqual(t.min_vertex_cover().size, 2)

    def test_path4_gives_two(self):
        t = build(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(t.independent_size(), 2)
        self.assertEqual(t.cover_size(), 2)

    def test_star_center_beats_leaves(self):
        t = build(4, STAR4)
        self.assertEqual(t.max_independent_set(), Solution([1, 2, 3]))
        self.assertEqual(t.min_vertex_cover(), Solution([0]))

    def test_star_leaf_priority_by_id(self):
        t = build(4, STAR4)
        self.assertEqual(t.max_independent_set().vertices, (1, 2, 3))

    def test_paw_has_triangle(self):
        t = build(4, PAW4)
        self.assertEqual(t.max_independent_set(), Solution([0, 3]))
        self.assertEqual(t.min_vertex_cover(), Solution([0, 2]))

    def test_two_vertices_one_edge(self):
        t = build(2, [(0, 1)])
        self.assertEqual(t.max_independent_set(), Solution([0]))
        self.assertEqual(t.min_vertex_cover(), Solution([0]))

    def test_two_vertices_no_edge_is_disconnected(self):
        t = build(2, [])
        self.assertEqual(t.max_independent_set(), Solution([0, 1]))
        self.assertEqual(t.min_vertex_cover(), Solution([]))

    def test_duplicate_edges_do_not_change_result(self):
        t = build(2, [(0, 1), (1, 0)])
        self.assertEqual(t.max_independent_set(), Solution([0]))
        self.assertEqual(t.min_vertex_cover(), Solution([0]))

    def test_tie_break_prefers_smaller_ids(self):
        t = build(3, [(0, 1), (1, 2)])
        got = t.max_independent_set()
        self.assertEqual(got.vertices, (0, 2))


class TestPredicates(unittest.TestCase):
    def test_is_independent_set(self):
        t = build(4, PATH4)
        self.assertTrue(t.is_independent_set([0, 2]))
        self.assertTrue(t.is_independent_set([1, 3]))
        self.assertFalse(t.is_independent_set([0, 1]))
        self.assertTrue(t.is_independent_set([]))

    def test_is_independent_set_dedups_input(self):
        t = build(4, PATH4)
        self.assertTrue(t.is_independent_set([0, 0, 2]))

    def test_is_vertex_cover(self):
        t = build(4, PATH4)
        self.assertTrue(t.is_vertex_cover([1, 2]))
        self.assertFalse(t.is_vertex_cover([0, 1]))
        self.assertFalse(t.is_vertex_cover([]))

    def test_empty_tree_is_covered(self):
        t = TreeSolve(0)
        self.assertTrue(t.is_vertex_cover([]))


class TestValidation(unittest.TestCase):
    def test_bad_vertex_count(self):
        with self.assertRaises(TreeInputError):
            TreeSolve(-1)

    def test_self_loop_rejected(self):
        t = TreeSolve(2)
        with self.assertRaises(TreeInputError):
            t.add_edge(0, 0)

    def test_unknown_vertex_on_edge(self):
        t = TreeSolve(2)
        with self.assertRaises(UnknownVertexError):
            t.add_edge(0, 5)

    def test_unknown_vertex_on_neighbors(self):
        t = TreeSolve(3)
        with self.assertRaises(UnknownVertexError):
            t.neighbors(7)

    def test_non_int_vertex(self):
        t = TreeSolve(2)
        with self.assertRaises(TreeInputError):
            t.add_edge(0, "1")

    def test_errors_share_base(self):
        t = TreeSolve(2)
        with self.assertRaises(Erro):
            t.add_edge(0, 9)
        with self.assertRaises(Erro):
            TreeSolve(-1)


if __name__ == "__main__":
    unittest.main()
