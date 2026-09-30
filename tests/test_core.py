"""基线测试：锁住改造前 LongChainTree 的现状行为。

这些用例描述的是当前"按子树节点数定重儿子、逐结点拷贝深度数组"实现
对外可见的事实，改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lcdecomp.core import (
    DisconnectedErro,
    Erro,
    InputErro,
    LongChainTree,
    UnknownNodeErro,
)


def build(n, edges, weights):
    tree = LongChainTree()
    tree.load(n, edges, weights)
    return tree


class TestLoadAndValidation(unittest.TestCase):
    def test_single_node_tree(self):
        tree = build(1, [], [7])
        self.assertEqual(tree.node_count(), 1)
        self.assertEqual(tree.depth_counts(0), [1])
        self.assertEqual(tree.deepest_depth(0), 0)

    def test_non_positive_n_rejected(self):
        with self.assertRaises(InputErro):
            build(0, [], [])

    def test_weights_length_mismatch_rejected(self):
        with self.assertRaises(InputErro):
            build(3, [(0, 1), (1, 2)], [1, 2])

    def test_negative_weight_rejected(self):
        with self.assertRaises(InputErro):
            build(2, [(0, 1)], [1, -1])

    def test_edge_endpoint_out_of_range_rejected(self):
        with self.assertRaises(InputErro):
            build(2, [(0, 5)], [1, 2])

    def test_wrong_edge_count_rejected(self):
        with self.assertRaises(DisconnectedErro):
            build(3, [(0, 1)], [1, 2, 3])

    def test_disconnected_edges_rejected(self):
        # 三条边连不成一棵覆盖 4 个结点的树: 结点 3 被孤立
        with self.assertRaises(DisconnectedErro):
            build(4, [(0, 1), (1, 2), (0, 2)], [1, 2, 3, 4])

    def test_query_before_load_rejected(self):
        with self.assertRaises(InputErro):
            LongChainTree().node_count()

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(InputErro, Erro))
        self.assertTrue(issubclass(UnknownNodeErro, Erro))
        self.assertTrue(issubclass(DisconnectedErro, Erro))


class TestHeavyChild(unittest.TestCase):
    def test_heaviest_by_node_count(self):
        # 0 的子结点 1、2；1 带两个后代，2 是叶子，故重儿子是 1
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [1, 1, 1, 1, 1])
        self.assertEqual(tree.heuristic_child(0), 1)

    def test_tie_breaks_to_smallest_id(self):
        # 0 的子结点 1、2 各为叶子，子树节点数并列，取编号较小者 1
        tree = build(3, [(0, 2), (0, 1)], [1, 1, 1])
        self.assertEqual(tree.heuristic_child(0), 1)

    def test_leaf_has_no_heaviest_child(self):
        tree = build(2, [(0, 1)], [1, 1])
        self.assertIsNone(tree.heuristic_child(1))


class TestDepthCounts(unittest.TestCase):
    def test_counts_on_small_tree(self):
        # 0 为根，子结点 1、2；1 的子结点 3、4
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)], [0, 0, 0, 0, 0])
        self.assertEqual(tree.depth_counts(0), [1, 2, 2])
        self.assertEqual(tree.depth_counts(1), [1, 2])
        self.assertEqual(tree.depth_counts(3), [1])

    def test_chain_depth_counts(self):
        # 链 0-1-2-3
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [1, 2, 3, 4])
        self.assertEqual(tree.depth_counts(0), [1, 1, 1, 1])
        self.assertEqual(tree.depth_counts(2), [1, 1])
        self.assertEqual(tree.deepest_depth(0), 3)
        self.assertEqual(tree.deepest_depth(3), 0)

    def test_star_depth_counts(self):
        # 星形: 0 为心，1、2、3 为叶
        tree = build(4, [(0, 1), (0, 2), (0, 3)], [8, 8, 8, 2])
        self.assertEqual(tree.depth_counts(0), [1, 3])

    def test_counts_returned_as_copy(self):
        tree = build(2, [(0, 1)], [1, 1])
        snap = tree.depth_counts(0)
        snap[0] = 999
        self.assertEqual(tree.depth_counts(0), [1, 1])

    def test_depth_distribution_uses_absolute_depth(self):
        # 0 之子 1，1 之子 2 与 3：深度 0 有 1 个，深度 1 有 1 个，深度 2 有 2 个
        tree = build(4, [(0, 1), (1, 2), (1, 3)], [1, 1, 1, 1])
        self.assertEqual(tree.depth_distribution(), [1, 1, 2])


class TestMergeCost(unittest.TestCase):
    def test_merge_cost_chain(self):
        # 链 0-1-2-3，各次合并搬运 3、5、7，合计 15
        tree = build(4, [(0, 1), (1, 2), (2, 3)], [1, 2, 3, 4])
        self.assertEqual(tree.merge_cost(), 15)

    def test_merge_cost_single_node(self):
        tree = build(1, [], [5])
        self.assertEqual(tree.merge_cost(), 0)


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_unknown_node_raises(self):
        tree = build(3, [(0, 1), (0, 2)], [1, 2, 3])
        with self.assertRaises(UnknownNodeErro):
            tree.depth_counts(9)
        with self.assertRaises(UnknownNodeErro):
            tree.deepest_depth(-1)

    def test_fixed_input_repeatable(self):
        edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]
        weights = [3, 1, 3, 2, 1, 2, 3]

        def run():
            tree = build(7, edges, weights)
            return (
                tree.depth_distribution(),
                tree.heuristic_child(0),
                tree.merge_cost(),
            )

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
