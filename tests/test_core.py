"""基线测试：锁住改造前 DsuTree 的现状行为。

这些用例描述的是当前"逐结点重走子树"实现对外可见的事实，
改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsutree.core import (
    DisconnectedError,
    DsuError,
    DsuInputError,
    DsuTree,
    UnknownNodeError,
)


def build(n, edges, colors):
    tree = DsuTree()
    tree.load(n, edges, colors)
    return tree


class TestLoadAndValidation(unittest.TestCase):
    def test_single_node_tree(self):
        tree = build(1, [], [7])
        self.assertEqual(tree.node_count(), 1)
        self.assertEqual(tree.subtree_counts(0), {7: 1})
        self.assertEqual(tree.dominant_color(0), 7)

    def test_non_positive_n_rejected(self):
        with self.assertRaises(DsuInputError):
            build(0, [], [])

    def test_colors_length_mismatch_rejected(self):
        with self.assertRaises(DsuInputError):
            build(3, [(0, 1), (1, 2)], [1, 2])

    def test_negative_color_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, [(0, 1)], [1, -1])

    def test_edge_endpoint_out_of_range_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, [(0, 5)], [1, 2])

    def test_wrong_edge_count_rejected(self):
        with self.assertRaises(DisconnectedError):
            build(3, [(0, 1)], [1, 2, 3])

    def test_disconnected_edges_rejected(self):
        # 三条边连不成一棵覆盖 4 个结点的树: 结点 3 被孤立
        with self.assertRaises(DisconnectedError):
            build(4, [(0, 1), (1, 2), (0, 2)], [1, 2, 3, 4])

    def test_query_before_load_rejected(self):
        with self.assertRaises(DsuInputError):
            DsuTree().node_count()


class TestSubtreeCounts(unittest.TestCase):
    def test_counts_on_small_tree(self):
        # 0 为根，子结点 1、2；1 的子结点 3、4
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [0, 1, 0, 1, 2])
        self.assertEqual(tree.subtree_counts(0), {0: 2, 1: 2, 2: 1})
        self.assertEqual(tree.subtree_counts(1), {1: 2, 2: 1})
        self.assertEqual(tree.subtree_counts(3), {1: 1})

    def test_counts_returns_copy(self):
        tree = build(2, [(0, 1)], [1, 1])
        snap = tree.subtree_counts(0)
        snap[1] = 999
        self.assertEqual(tree.subtree_counts(0), {1: 2})

    def test_all_subtree_counts(self):
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [0, 1, 0, 1, 2])
        table = tree.all_subtree_counts()
        self.assertEqual(table[0], {0: 2, 1: 2, 2: 1})
        self.assertEqual(table[4], {2: 1})


class TestDominantColor(unittest.TestCase):
    def test_tie_breaks_to_smallest_color(self):
        # 结点 0 子树颜色 5 与 3 各出现一次，应取 3
        tree = build(2, [(0, 1)], [5, 3])
        self.assertEqual(tree.subtree_counts(0), {5: 1, 3: 1})
        self.assertEqual(tree.dominant_color(0), 3)
        self.assertEqual(tree.dominant_color(1), 3)

    def test_all_colors_same(self):
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [9, 9, 9, 9])
        self.assertEqual(tree.dominant_color(0), 9)
        self.assertEqual(tree.dominant_color(3), 9)

    def test_all_colors_distinct(self):
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [4, 3, 2, 1])
        # 子树各色只出现一次，取编号最小者
        self.assertEqual(tree.dominant_color(0), 1)
        self.assertEqual(tree.dominant_color(2), 1)

    def test_all_dominant_colors(self):
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [0, 1, 0, 1, 2])
        self.assertEqual(
            tree.all_dominant_colors(), {0: 0, 1: 1, 2: 0, 3: 1, 4: 2}
        )


class TestChainAndStar(unittest.TestCase):
    def test_chain_tree(self):
        # 链 0-1-2-3，颜色 1、2、2、3
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [1, 2, 2, 3])
        self.assertEqual(tree.subtree_counts(0), {1: 1, 2: 2, 3: 1})
        self.assertEqual(tree.dominant_color(0), 2)
        self.assertEqual(tree.subtree_counts(3), {3: 1})

    def test_star_tree(self):
        # 星形: 0 为心，1、2、3 为叶
        tree = build(4, [(0, 1), (0, 2), (0, 3)], [8, 8, 8, 2])
        self.assertEqual(tree.dominant_color(0), 8)
        self.assertEqual(tree.dominant_color(3), 2)


class TestVisitCountAndErrors(unittest.TestCase):
    def test_visit_count_chain(self):
        # 链 0-1-2-3 的子树规模之和为 4+3+2+1 = 10
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [1, 2, 3, 4])
        self.assertEqual(tree.visit_count(), 10)

    def test_unknown_node_raises(self):
        tree = build(3, [(0, 1), (0, 2)], [1, 2, 3])
        with self.assertRaises(UnknownNodeError):
            tree.subtree_counts(9)
        with self.assertRaises(UnknownNodeError):
            tree.dominant_color(-1)

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(DsuInputError, DsuError))
        self.assertTrue(issubclass(UnknownNodeError, DsuError))
        self.assertTrue(issubclass(DisconnectedError, DsuError))


class TestDeterminism(unittest.TestCase):
    def test_fixed_input_repeatable(self):
        edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]
        colors = [3, 1, 3, 2, 1, 2, 3]

        def run():
            tree = build(7, edges, colors)
            return tree.all_dominant_colors(), tree.all_subtree_counts()

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
