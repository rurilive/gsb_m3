"""UnionFind 现有行为的锁定测试（朴素逐元素搬移口径）。"""

import unittest

from unionfind.core import (
    IllegalRollback,
    NotConnected,
    UnionFind,
    UnionFindError,
    UnionFindInputError,
    UnknownNode,
)


def fresh():
    """登记 0 到 5 共六个孤立元素。"""
    uf = UnionFind()
    for x in range(6):
        uf.add(x)
    return uf


class TestAdd(unittest.TestCase):
    def test_elements_sorted(self):
        uf = fresh()
        self.assertEqual(uf.elements(), [0, 1, 2, 3, 4, 5])

    def test_add_is_idempotent(self):
        uf = fresh()
        uf.union(0, 1)
        uf.add(0)
        self.assertEqual(uf.group_members(0), [0, 1])

    def test_contains(self):
        uf = fresh()
        self.assertTrue(uf.contains(3))
        self.assertFalse(uf.contains(9))

    def test_negative_element_rejected(self):
        uf = UnionFind()
        with self.assertRaises(UnionFindInputError):
            uf.add(-1)

    def test_non_int_element_rejected(self):
        uf = UnionFind()
        with self.assertRaises(UnionFindInputError):
            uf.add("x")


class TestQuery(unittest.TestCase):
    def test_singleton_is_own_root(self):
        uf = fresh()
        self.assertEqual(uf.find(0), 0)

    def test_unknown_node_rejected(self):
        uf = fresh()
        with self.assertRaises(UnknownNode):
            uf.find(99)

    def test_unknown_node_is_base_error(self):
        uf = fresh()
        with self.assertRaises(UnionFindError):
            uf.find(99)

    def test_connected_same_point(self):
        uf = fresh()
        self.assertTrue(uf.connected(2, 2))

    def test_disconnected_pair(self):
        uf = fresh()
        self.assertFalse(uf.connected(0, 1))

    def test_size_of_singleton(self):
        uf = fresh()
        self.assertEqual(uf.size(4), 1)

    def test_rank_of_singleton(self):
        uf = fresh()
        self.assertEqual(uf.rank(4), 0)

    def test_group_members_sorted(self):
        uf = fresh()
        uf.union(3, 5)
        uf.union(3, 4)
        self.assertEqual(uf.group_members(3), [3, 4, 5])


class TestUnion(unittest.TestCase):
    def test_union_returns_true_once(self):
        uf = fresh()
        self.assertTrue(uf.union(0, 1))
        self.assertFalse(uf.union(0, 1))

    def test_union_makes_connected(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(2, 3)
        uf.union(1, 2)
        self.assertTrue(uf.connected(0, 3))

    def test_self_union_is_noop(self):
        uf = fresh()
        self.assertFalse(uf.union(2, 2))
        self.assertEqual(uf.group_members(2), [2])

    def test_size_grows(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.size(0), 3)

    def test_rank_chain(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(1, 2)
        # 朴素搬移把成员直接挂到根上，深度保持为一
        self.assertEqual(uf.rank(0), 1)
        self.assertEqual(uf.find(2), 0)

    def test_component_count(self):
        uf = fresh()
        self.assertEqual(uf.component_count(), 6)
        uf.union(0, 1)
        self.assertEqual(uf.component_count(), 5)

    def test_component_sizes_sorted(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.component_sizes(), [1, 1, 1, 3])

    def test_groups_ordered_by_min_member(self):
        uf = fresh()
        uf.union(4, 5)
        uf.union(0, 1)
        self.assertEqual(uf.groups(), [[0, 1], [2], [3], [4, 5]])


class TestWeighted(unittest.TestCase):
    def test_weighted_union_and_relate(self):
        uf = fresh()
        uf.union_weighted(1, 0, 5)
        self.assertEqual(uf.relate(1, 0), 5)

    def test_negative_weight(self):
        uf = fresh()
        uf.union_weighted(1, 0, -3)
        self.assertEqual(uf.relate(1, 0), -3)

    def test_zero_weight(self):
        uf = fresh()
        uf.union_weighted(1, 0, 0)
        self.assertEqual(uf.relate(1, 0), 0)

    def test_transitive_offsets(self):
        uf = fresh()
        uf.union_weighted(1, 0, 2)
        uf.union_weighted(2, 1, 3)
        self.assertEqual(uf.relate(2, 0), 5)
        self.assertEqual(uf.relate(2, 1), 3)

    def test_relate_disconnected_raises(self):
        uf = fresh()
        with self.assertRaises(NotConnected):
            uf.relate(0, 1)

    def test_non_int_weight_rejected(self):
        uf = fresh()
        with self.assertRaises(UnionFindInputError):
            uf.union_weighted(0, 1, 1.5)


class TestHistory(unittest.TestCase):
    def test_history_len(self):
        uf = fresh()
        self.assertEqual(uf.history_len(), 0)
        uf.union(0, 1)
        self.assertEqual(uf.history_len(), 1)

    def test_undo_restores_connectivity(self):
        uf = fresh()
        uf.union(0, 1)
        uf.undo()
        self.assertFalse(uf.connected(0, 1))
        self.assertEqual(uf.component_count(), 6)

    def test_undo_empty_is_noop(self):
        uf = fresh()
        self.assertFalse(uf.undo())

    def test_rollback_to_zero(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(1, 2)
        uf.rollback_to(0)
        self.assertEqual(uf.history_len(), 0)
        self.assertFalse(uf.connected(0, 1))

    def test_rollback_out_of_range(self):
        uf = fresh()
        uf.union(0, 1)
        with self.assertRaises(IllegalRollback):
            uf.rollback_to(5)

    def test_undo_weighted_restores_offset(self):
        uf = fresh()
        uf.union_weighted(1, 0, 4)
        uf.undo()
        with self.assertRaises(NotConnected):
            uf.relate(1, 0)

    def test_connected_at(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(2, 3)
        self.assertTrue(uf.connected_at(1, 0, 1))
        self.assertFalse(uf.connected_at(1, 2, 3))
        self.assertTrue(uf.connected_at(2, 2, 3))


class TestCost(unittest.TestCase):
    def test_moves_count(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.count_moves(), 2)

    def test_visits_grow_with_find(self):
        uf = fresh()
        uf.union(0, 1)
        before = uf.count_visits()
        uf.find(1)
        self.assertGreater(uf.count_visits(), before)

    def test_cost_report_keys(self):
        uf = fresh()
        self.assertEqual(sorted(uf.cost_report()), ["moves", "visits"])


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_sequence(self):
        seq = [(0, 1), (2, 3), (1, 2), (4, 5), (3, 4)]
        first = fresh()
        second = fresh()
        for a, b in seq:
            first.union(a, b)
            second.union(a, b)
        self.assertEqual(first.groups(), second.groups())
        self.assertEqual(first.count_moves(), second.count_moves())

    def test_groups_stable_on_repeat(self):
        uf = fresh()
        uf.union(0, 1)
        self.assertEqual(uf.groups(), uf.groups())


if __name__ == "__main__":
    unittest.main()
