"""基线测试：锁住改造前 treeknapsack.knapsack.TreeKnapsack 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - brute_best 逐个考虑物品选与不选，累积重量与价值，记录最优；
  - brute_exact 只在选中物品恰好装满容量时取最优；
  - brute_subtree 对子树内每个节点单独枚举取数组合，再对子树整体取最优；
  - brute_all_subtrees 把每个节点当子树根各算一次，按编号升序返回；
  - 依赖闭合判定自己沿父指针走到根逐项检查祖先；
  - forest_count 与 is_forest 描述多根的情形；
  - brute_visits 随调用规模累加，是留给升级路径对账的锚。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from treeknapsack.knapsack import (  # noqa: E402
    TreeKnapsack,
    Metric,
    Erro,
    SizeErro,
    GraphErro,
    WeightErro,
    CapacityErro,
    MAX_CAP,
    MAX_ITEMS,
)


def _sample():
    # 0 为根，1、2 挂在 0，3 挂在 1。
    return TreeKnapsack(4, [-1, 0, 0, 1], [2, 3, 1, 4], [3, 4, 5, 6], 5)


class TestConstruction(unittest.TestCase):
    def test_basic(self):
        p = _sample()
        self.assertEqual(p.n, 4)
        self.assertEqual(p.parent, [-1, 0, 0, 1])
        self.assertEqual(p.cap, 5)

    def test_children_and_roots(self):
        p = _sample()
        self.assertEqual(p.children, [[1, 2], [3], [], []])
        self.assertEqual(p.roots, [0])

    def test_negative_n(self):
        with self.assertRaises(SizeErro):
            TreeKnapsack(-1, [], [], [], 0)

    def test_bool_is_not_int(self):
        with self.assertRaises(SizeErro):
            TreeKnapsack(True, [], [], [], 0)

    def test_bool_cap_is_not_int(self):
        with self.assertRaises(CapacityErro):
            TreeKnapsack(2, [-1, -1], [1, 1], [1, 1], True)

    def test_n_over_max(self):
        with self.assertRaises(SizeErro):
            TreeKnapsack(MAX_ITEMS + 1, [-1] * (MAX_ITEMS + 1),
                         [1] * (MAX_ITEMS + 1), [1] * (MAX_ITEMS + 1), 1)

    def test_parent_length_mismatch(self):
        with self.assertRaises(SizeErro):
            TreeKnapsack(2, [-1], [1, 1], [1, 1], 1)

    def test_parent_not_int(self):
        with self.assertRaises(GraphErro):
            TreeKnapsack(2, [-1, "a"], [1, 1], [1, 1], 1)

    def test_parent_out_of_range(self):
        with self.assertRaises(GraphErro):
            TreeKnapsack(2, [-1, 5], [1, 1], [1, 1], 1)

    def test_parent_self_loop(self):
        with self.assertRaises(GraphErro):
            TreeKnapsack(2, [-1, 1], [1, 1], [1, 1], 1)

    def test_parent_cycle(self):
        with self.assertRaises(GraphErro):
            TreeKnapsack(3, [1, 2, 0], [1, 1, 1], [1, 1, 1], 1)

    def test_weight_length_mismatch(self):
        with self.assertRaises(WeightErro):
            TreeKnapsack(2, [-1, -1], [1], [1, 1], 1)

    def test_negative_weight(self):
        with self.assertRaises(WeightErro):
            TreeKnapsack(2, [-1, -1], [1, -1], [1, 1], 1)

    def test_value_length_mismatch(self):
        with self.assertRaises(WeightErro):
            TreeKnapsack(2, [-1, -1], [1, 1], [1], 1)

    def test_negative_cap(self):
        with self.assertRaises(CapacityErro):
            TreeKnapsack(1, [-1], [1], [1], -1)


class TestBruteBest(unittest.TestCase):
    def test_sample(self):
        p = _sample()
        self.assertEqual(p.brute_best(), (8, [0, 2]))

    def test_star(self):
        p = TreeKnapsack(4, [-1, 0, 0, 0], [1, 1, 1, 1], [1, 2, 3, 4], 3)
        self.assertEqual(p.brute_best(), (8, [0, 2, 3]))

    def test_chain(self):
        p = TreeKnapsack(4, [-1, 0, 1, 2], [1, 1, 1, 1], [1, 2, 3, 4], 3)
        self.assertEqual(p.brute_best(), (6, [0, 1, 2]))

    def test_single(self):
        self.assertEqual(
            TreeKnapsack(1, [-1], [3], [9], 5).brute_best(), (9, [0]))

    def test_single_overweight(self):
        self.assertEqual(
            TreeKnapsack(1, [-1], [9], [9], 5).brute_best(), (0, []))

    def test_child_without_parent_not_allowed(self):
        # 3 挂在 1 上，1 不选时 3 不可选；1 重 3 超过容量，只能选 0 与 2。
        p = TreeKnapsack(2, [-1, 0], [1, 9], [5, 9], 1)
        self.assertEqual(p.brute_best(), (5, [0]))

    def test_empty_tree(self):
        self.assertEqual(TreeKnapsack(0, [], [], [], 0).brute_best(), (0, []))

    def test_zero_weight_all_taken(self):
        p = TreeKnapsack(3, [-1, 0, 0], [0, 0, 0], [5, 6, 7], 0)
        self.assertEqual(p.brute_best(), (18, [0, 1, 2]))

    def test_tie_takes_lexicographic(self):
        # 两个物品并列，编号字典序最小的集合胜出。
        p = TreeKnapsack(2, [-1, -1], [1, 1], [5, 5], 1)
        self.assertEqual(p.brute_best(), (5, [0]))


class TestBruteExact(unittest.TestCase):
    def test_exact_hit(self):
        self.assertEqual(_sample().brute_exact(5), (7, [0, 1]))

    def test_exact_hit_cap3(self):
        p = TreeKnapsack(3, [-1, 0, 0], [1, 1, 2], [3, 4, 5], 3)
        self.assertEqual(p.brute_exact(3), (8, [0, 2]))

    def test_exact_impossible(self):
        # 容量四凑不出，恰好口径返回空。
        self.assertEqual(_sample().brute_exact(4), (None, []))

    def test_exact_cap_too_large(self):
        self.assertEqual(_sample().brute_exact(100), (None, []))

    def test_exact_cap_zero_all_zero_weight(self):
        p = TreeKnapsack(3, [-1, 0, 0], [0, 0, 0], [5, 6, 7], 0)
        self.assertEqual(p.brute_exact(0), (18, [0, 1, 2]))

    def test_exact_rejects_negative(self):
        with self.assertRaises(CapacityErro):
            _sample().brute_exact(-1)


class TestBruteSubtree(unittest.TestCase):
    def test_subtree_of_root(self):
        p = _sample()
        self.assertEqual(p.brute_subtree(0, 5), (8, [0, 2]))

    def test_subtree_of_leaf(self):
        p = _sample()
        self.assertEqual(p.brute_subtree(3, 5), (6, [3]))

    def test_subtree_root_is_standalone(self):
        # 子树根独立看待：只要自身重量不超容量就可入选，不必带上祖先。
        p = _sample()
        self.assertEqual(p.brute_subtree(1, 5), (4, [1]))
        self.assertEqual(p.brute_subtree(2, 5), (5, [2]))

    def test_subtree_no_item_fits(self):
        # 重量都超过容量，最优为一件不选，价值零、集合空。
        p = TreeKnapsack(2, [-1, 0], [9, 9], [1, 2], 5)
        self.assertEqual(p.brute_subtree(0, 5), (0, []))

    def test_all_subtrees_ascending(self):
        p = _sample()
        self.assertEqual(p.brute_all_subtrees(5), [8, 4, 5, 6])

    def test_all_subtrees_star(self):
        p = TreeKnapsack(4, [-1, 0, 0, 0], [1, 1, 1, 1], [1, 2, 3, 4], 3)
        self.assertEqual(p.brute_all_subtrees(3), [8, 2, 3, 4])

    def test_all_subtrees_chain(self):
        p = TreeKnapsack(4, [-1, 0, 1, 2], [1, 1, 1, 1], [1, 2, 3, 4], 3)
        self.assertEqual(p.brute_all_subtrees(3), [6, 9, 7, 4])

    def test_all_subtrees_empty(self):
        self.assertEqual(TreeKnapsack(0, [], [], [], 0).brute_all_subtrees(0), [])

    def test_subtree_root_out_of_range(self):
        with self.assertRaises(SizeErro):
            _sample().brute_subtree(9, 5)


class TestForest(unittest.TestCase):
    def test_forest_roots(self):
        p = TreeKnapsack(4, [-1, 2, -1, 2], [1, 1, 1, 1], [1, 2, 3, 4], 3)
        self.assertEqual(p.roots, [0, 2])
        self.assertTrue(p.is_forest())
        self.assertEqual(p.forest_count(), 2)

    def test_single_tree_is_not_forest(self):
        p = _sample()
        self.assertFalse(p.is_forest())
        self.assertEqual(p.forest_count(), 1)

    def test_empty_is_forest(self):
        p = TreeKnapsack(0, [], [], [], 0)
        self.assertTrue(p.is_forest())
        self.assertEqual(p.forest_count(), 0)


class TestScaleMetrics(unittest.TestCase):
    def test_visits_positive(self):
        p = _sample()
        p.brute_best()
        self.assertGreater(p.brute_visits, 0)

    def test_fresh_instance_zero(self):
        self.assertEqual(_sample().brute_visits, 0)

    def test_counts_reset_between_calls(self):
        p = _sample()
        p.brute_best()
        first = p.brute_visits
        p.brute_best()
        self.assertEqual(p.brute_visits, first)

    def test_bigger_input_more_visits(self):
        small = TreeKnapsack(3, [-1, 0, 0], [1, 1, 1], [1, 1, 1], 3)
        large = TreeKnapsack(6, [-1, 0, 0, 0, 0, 0], [1] * 6, [1] * 6, 6)
        small.brute_best()
        large.brute_best()
        self.assertGreater(large.brute_visits, small.brute_visits)


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = _sample().brute_best()
        b = _sample().brute_best()
        self.assertEqual(a, b)

    def test_all_subtrees_repeated(self):
        p = _sample()
        self.assertEqual(p.brute_all_subtrees(5), p.brute_all_subtrees(5))

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SizeErro, Erro))
        self.assertTrue(issubclass(GraphErro, Erro))
        self.assertTrue(issubclass(WeightErro, Erro))
        self.assertTrue(issubclass(CapacityErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))

    def test_metric_values(self):
        self.assertEqual(Metric.EXACT.value, "exact")
        self.assertEqual(Metric.AT_MOST.value, "at_most")

    def test_max_limits_exported(self):
        self.assertEqual(MAX_ITEMS, 14)
        self.assertEqual(MAX_CAP, 24)


if __name__ == "__main__":
    unittest.main()
