"""TreeKnapsack 现有行为的锁定测试（朴素暴力枚举口径）。"""

import unittest

from treedpx.core import (
    TreeError,
    TreeInputError,
    TreeKnapsack,
    UnknownNode,
)


def chain():
    """a -> b -> c 的链状树，重量各 1，价值 1 / 2 / 3。"""
    return (
        {"a": (1, 1), "b": (1, 2), "c": (1, 3)},
        {"a": None, "b": "a", "c": "b"},
    )


class TestLoad(unittest.TestCase):
    def test_load_and_nodes_sorted(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        self.assertEqual(k.nodes(), ["a", "b", "c"])

    def test_nodes_is_deterministic(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        self.assertEqual(k.nodes(), k.nodes())

    def test_parent_of_root_is_none(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        self.assertIsNone(k.parent_of("a"))
        self.assertEqual(k.parent_of("c"), "b")

    def test_parent_of_unknown_raises(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        with self.assertRaises(UnknownNode):
            k.parent_of("ghost")

    def test_empty_nodes_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.load({}, {})

    def test_non_integer_weight_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.load({"a": ("1", 2)}, {"a": None})

    def test_negative_weight_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.load({"a": (-1, 2)}, {"a": None})

    def test_missing_parent_entry_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.load({"a": (1, 1)}, {})

    def test_unknown_parent_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(UnknownNode):
            k.load({"a": (1, 1)}, {"a": "ghost"})

    def test_cycle_rejected(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.load({"a": (1, 1), "b": (1, 1)}, {"a": "b", "b": "a"})

    def test_use_before_load_raises(self):
        k = TreeKnapsack()
        with self.assertRaises(TreeInputError):
            k.brute_force_best(5)


class TestSingleNode(unittest.TestCase):
    def test_capacity_zero_blocks_positive_weight(self):
        k = TreeKnapsack()
        k.load({"a": (2, 7)}, {"a": None})
        self.assertEqual(k.brute_force_best(0), 0)
        self.assertEqual(k.brute_force_selection(0), [])
        self.assertEqual(k.feasible_count(0), 1)

    def test_capacity_enough_takes_node(self):
        k = TreeKnapsack()
        k.load({"a": (2, 7)}, {"a": None})
        self.assertEqual(k.brute_force_best(2), 7)
        self.assertEqual(k.brute_force_selection(2), ["a"])
        self.assertEqual(k.feasible_count(2), 2)


class TestChainTree(unittest.TestCase):
    def test_parent_must_be_chosen(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        # 容量 2 只放得下两个节点，且 c 必须先有 b、b 必须先有 a
        self.assertEqual(k.brute_force_best(2), 3)
        self.assertEqual(k.brute_force_selection(2), ["a", "b"])

    def test_feasible_count(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        # {}、{a}、{a,b}、{a,b,c} 四种合法组合里，容量 2 容得下前三种
        self.assertEqual(k.feasible_count(2), 3)
        self.assertEqual(k.feasible_count(3), 4)


class TestZeroWeight(unittest.TestCase):
    def test_zero_weight_node_still_selectable(self):
        k = TreeKnapsack()
        k.load({"a": (0, 5)}, {"a": None})
        self.assertEqual(k.brute_force_best(0), 5)
        self.assertEqual(k.brute_force_selection(0), ["a"])
        self.assertEqual(k.feasible_count(0), 2)


class TestStarTree(unittest.TestCase):
    def test_root_then_leaves(self):
        nodes = {"r": (1, 1), "x": (1, 10), "y": (1, 20), "z": (4, 50)}
        parent = {"r": None, "x": "r", "y": "r", "z": "r"}
        k = TreeKnapsack()
        k.load(nodes, parent)
        # 容量 2：只能选根加一个孩子，y 最优
        self.assertEqual(k.brute_force_best(2), 21)
        self.assertEqual(k.brute_force_selection(2), ["r", "y"])


class TestScale(unittest.TestCase):
    def test_brute_force_scale(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        self.assertEqual(k.brute_force_scale(), 8)

    def test_state_scale_not_implemented(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        with self.assertRaises(NotImplementedError):
            k.state_scale(2)


class TestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(TreeInputError, TreeError))
        self.assertTrue(issubclass(UnknownNode, TreeError))

    def test_repeat_runs_identical(self):
        nodes, parent = chain()
        k = TreeKnapsack()
        k.load(nodes, parent)
        first = (k.brute_force_best(2), k.brute_force_selection(2), k.feasible_count(2))
        second = (k.brute_force_best(2), k.brute_force_selection(2), k.feasible_count(2))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
