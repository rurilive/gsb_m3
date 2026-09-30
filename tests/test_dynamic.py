"""基线测试：锁住改造前 segmerge.dynamic.MergeTree 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - 子节点的集合逐个元素追加进父节点的桶，自底向上合并整棵树；
  - 每搬一个元素都把朴素搬移计数加一，链状树自底向上是平方量级；
  - 合并后整体排序一次，统计都在排序桶上从头扫过；
  - 空集合上取第几小、k 越界、非法节点号、非法权值、非法树形各抛对应异常；
  - 同一实例反复调用结果一致，固定输入重复跑结果完全相同。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from segmerge.dynamic import (  # noqa: E402
    BadWeightError,
    EmptySetError,
    KOutOfRangeError,
    MergeSegError,
    MergeTree,
    NodeIndexError,
    TreeShapeError,
)


def sample_tree():
    """节点 0 为根，子节点 1、2；节点 1 的子节点 3、4。

    本地小集合：0:[5] 1:[2,2] 2:[7] 3:[-3] 4:[]，合并后按升序：
    0:[-3,2,2,5,7] 1:[-3,2,2] 2:[7] 3:[-3] 4:[]
    """
    parents = [-1, 0, 0, 1, 1]
    weights = [[5], [2, 2], [7], [-3], []]
    return MergeTree(parents, weights)


class TestNaiveMerge(unittest.TestCase):
    def test_merged_values_are_sorted_multiset(self):
        t = sample_tree()
        self.assertEqual(t.merged_values(0), [-3, 2, 2, 5, 7])
        self.assertEqual(t.merged_values(1), [-3, 2, 2])
        self.assertEqual(t.merged_values(2), [7])
        self.assertEqual(t.merged_values(3), [-3])
        self.assertEqual(t.merged_values(4), [])

    def test_size_counts_duplicates(self):
        t = sample_tree()
        self.assertEqual(t.size(0), 5)
        self.assertEqual(t.size(1), 3)
        self.assertEqual(t.size(4), 0)

    def test_merged_values_is_a_copy(self):
        t = sample_tree()
        got = t.merged_values(0)
        got[0] = 999
        self.assertEqual(t.merged_values(0)[0], -3)

    def test_local_weights_is_a_copy(self):
        t = sample_tree()
        got = t.local_weights(1)
        got.append(123)
        self.assertEqual(t.local_weights(1), [2, 2])

    def test_root_and_children(self):
        t = sample_tree()
        self.assertEqual(t.node_count(), 5)
        self.assertEqual(t.root(), 0)
        self.assertEqual(t.children(0), [1, 2])
        self.assertEqual(t.children(1), [3, 4])
        self.assertEqual(t.children(3), [])


class TestNaiveStats(unittest.TestCase):
    def test_count_of(self):
        t = sample_tree()
        self.assertEqual(t.count_of(0, 2), 2)
        self.assertEqual(t.count_of(1, 2), 2)
        self.assertEqual(t.count_of(0, 9), 0)

    def test_topk_sum(self):
        t = sample_tree()
        self.assertEqual(t.topk_sum(0, 0), 0)
        self.assertEqual(t.topk_sum(0, 2), 12)
        self.assertEqual(t.topk_sum(0, 5), 13)
        self.assertEqual(t.topk_sum(1, 1), 2)

    def test_distinct_count(self):
        t = sample_tree()
        self.assertEqual(t.distinct_count(0), 4)
        self.assertEqual(t.distinct_count(1), 2)
        self.assertEqual(t.distinct_count(4), 0)

    def test_rank_of(self):
        t = sample_tree()
        self.assertEqual(t.rank_of(0, -3), 1)
        self.assertEqual(t.rank_of(0, 2), 2)
        self.assertEqual(t.rank_of(0, 5), 4)
        self.assertEqual(t.rank_of(0, 7), 5)
        # 6 一个也没有，按「比它小的个数加一」给出 5
        self.assertEqual(t.rank_of(0, 6), 5)

    def test_kth_smallest(self):
        t = sample_tree()
        self.assertEqual(t.kth_smallest(0, 1), -3)
        self.assertEqual(t.kth_smallest(0, 3), 2)
        self.assertEqual(t.kth_smallest(0, 5), 7)

    def test_merge_report(self):
        t = sample_tree()
        report = t.merge_report()
        self.assertEqual(report[0],
                         {"total": 5, "distinct": 4, "min": -3, "max": 7})
        self.assertEqual(report[1],
                         {"total": 3, "distinct": 2, "min": -3, "max": 2})
        self.assertEqual(report[4],
                         {"total": 0, "distinct": 0,
                          "min": None, "max": None})

    def test_report_is_a_fresh_dict(self):
        t = sample_tree()
        report = t.merge_report()
        report[0]["total"] = 999
        self.assertEqual(t.merge_report()[0]["total"], 5)


class TestNaiveMoveCount(unittest.TestCase):
    def test_chain_moves_are_quadratic_ish(self):
        # 链 0-1-2-3，每点本地就一个元素，自底向上逐个搬：
        # 3->2 搬 1 个，2->1 再搬 2 个，1->0 再搬 3 个，共 6 次
        t = MergeTree([-1, 0, 1, 2], [[0], [1], [2], [3]])
        self.assertEqual(t.size(0), 4)
        self.assertEqual(t.naive_moves(), 6)

    def test_empty_child_costs_nothing(self):
        t = MergeTree([-1, 0], [[1], []])
        self.assertEqual(t.size(0), 1)
        self.assertEqual(t.naive_moves(), 0)

    def test_clear_cache_refreshes_moves(self):
        t = MergeTree([-1, 0], [[1], [2]])
        t.size(0)
        first = t.naive_moves()
        t.clear_cache()
        t.size(0)
        self.assertEqual(t.naive_moves(), first + 1)


class TestBaselineEdges(unittest.TestCase):
    def test_single_node(self):
        t = MergeTree([-1], [[42]])
        self.assertEqual(t.merged_values(0), [42])
        self.assertEqual(t.count_of(0, 42), 1)
        self.assertEqual(t.kth_smallest(0, 1), 42)
        self.assertEqual(t.naive_moves(), 0)

    def test_all_same_weight(self):
        t = MergeTree([-1, 0, 0], [[7], [7], [7, 7]])
        self.assertEqual(t.merged_values(0), [7, 7, 7, 7])
        self.assertEqual(t.count_of(0, 7), 4)
        self.assertEqual(t.distinct_count(0), 1)
        self.assertEqual(t.topk_sum(0, 3), 21)

    def test_negative_and_large_weights(self):
        t = MergeTree([-1, 0],
                      [[-1000000000000, -1], [10 ** 18]])
        self.assertEqual(t.merged_values(0), [-1000000000000, -1, 10 ** 18])
        self.assertEqual(t.rank_of(0, -1), 2)
        self.assertEqual(t.kth_smallest(0, 1), -1000000000000)

    def test_empty_tree(self):
        t = MergeTree([], [])
        self.assertEqual(t.node_count(), 0)
        self.assertIsNone(t.root())
        self.assertEqual(t.merge_report(), {})

    def test_empty_set_node(self):
        t = MergeTree([-1], [[]])
        self.assertEqual(t.size(0), 0)
        self.assertEqual(t.distinct_count(0), 0)
        with self.assertRaises(EmptySetError):
            t.kth_smallest(0, 1)


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (NodeIndexError, BadWeightError, TreeShapeError,
                    EmptySetError, KOutOfRangeError):
            self.assertTrue(issubclass(exc, MergeSegError))

    def test_bad_node_id(self):
        t = sample_tree()
        with self.assertRaises(NodeIndexError):
            t.size(5)
        with self.assertRaises(NodeIndexError):
            t.children(-1)
        with self.assertRaises(NodeIndexError):
            t.count_of("x", 1)

    def test_bad_weight(self):
        with self.assertRaises(BadWeightError):
            MergeTree([-1], [[1.5]])
        t = sample_tree()
        with self.assertRaises(BadWeightError):
            t.count_of(0, True)
        with self.assertRaises(BadWeightError):
            t.rank_of(0, "z")

    def test_k_out_of_range(self):
        t = sample_tree()
        with self.assertRaises(KOutOfRangeError):
            t.topk_sum(0, 6)
        with self.assertRaises(KOutOfRangeError):
            t.topk_sum(0, -1)
        with self.assertRaises(KOutOfRangeError):
            t.kth_smallest(0, 0)
        with self.assertRaises(KOutOfRangeError):
            t.kth_smallest(0, 6)

    def test_bad_tree_shape(self):
        with self.assertRaises(TreeShapeError):
            MergeTree([-1, -1], [[1], [2]])          # 两个根
        with self.assertRaises(TreeShapeError):
            MergeTree([1, 0], [[1], [2]])            # 成环无根
        with self.assertRaises(TreeShapeError):
            MergeTree([0, 0], [[1], [2]])            # 自指
        with self.assertRaises(TreeShapeError):
            MergeTree([-1, 5], [[1], [2]])           # 父节点越界
        with self.assertRaises(TreeShapeError):
            MergeTree([-1], [])                      # 长度不一致


class TestBaselineDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        def run():
            t = sample_tree()
            return (t.merged_values(0),
                    t.topk_sum(0, 2),
                    t.rank_of(0, 2),
                    t.merge_report(),
                    t.naive_moves())

        self.assertEqual(run(), run())

    def test_no_cross_call_residue(self):
        t = sample_tree()
        first = t.merged_values(0)
        second = t.merged_values(0)
        self.assertEqual(first, second)
        self.assertEqual(t.naive_moves(), t.naive_moves())


if __name__ == "__main__":
    unittest.main()
