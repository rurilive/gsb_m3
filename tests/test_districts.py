"""基线测试：锁住改造前 RollbackDSU 的现状行为。

这些用例描述的是当前"搬到动方、回滚整表重算"实现对外可见的事实，
改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbdsu.districts import (
    DsuInputError,
    Erro,
    NoCheckpointError,
    RollbackDSU,
    UnknownElemError,
)


def build(n, labels=None):
    return RollbackDSU(n, labels)


class TestConstruction(unittest.TestCase):
    def test_empty_forest(self):
        d = build(0)
        self.assertEqual(d.count(), 0)
        self.assertEqual(d.group_count(), 0)
        self.assertEqual(d.groups(), [])

    def test_single_element(self):
        d = build(1, ["solo"])
        self.assertEqual(d.count(), 1)
        self.assertEqual(d.size("solo"), 1)
        self.assertEqual(d.members("solo"), ["solo"])
        self.assertEqual(d.groups(), [["solo"]])
        self.assertTrue(d.connected("solo", "solo"))

    def test_default_labels_are_strings(self):
        d = build(3)
        self.assertEqual(d.members("0"), ["0"])
        self.assertEqual(d.members("2"), ["2"])

    def test_each_element_starts_alone(self):
        d = build(4, list("abcd"))
        self.assertEqual(d.group_count(), 4)
        self.assertFalse(d.connected("a", "b"))
        self.assertEqual(d.groups(), [["a"], ["b"], ["c"], ["d"]])


class TestUnionAndQueries(unittest.TestCase):
    def test_union_merges_two_sets(self):
        d = build(4, list("abcd"))
        self.assertTrue(d.union("a", "b"))
        self.assertTrue(d.connected("a", "b"))
        self.assertEqual(d.size("a"), 2)
        self.assertEqual(d.size("b"), 2)
        self.assertEqual(d.members("a"), ["a", "b"])
        self.assertEqual(d.group_count(), 3)

    def test_union_across_groups(self):
        d = build(5, list("abcde"))
        d.union("a", "b")
        d.union("c", "d")
        d.union("b", "c")
        self.assertTrue(d.connected("a", "d"))
        self.assertTrue(d.connected("e", "e"))
        self.assertFalse(d.connected("a", "e"))
        self.assertEqual(d.members("d"), ["a", "b", "c", "d"])
        self.assertEqual(d.groups(), [["a", "b", "c", "d"], ["e"]])

    def test_duplicate_union_is_noop(self):
        d = build(3, list("abc"))
        self.assertTrue(d.union("a", "b"))
        self.assertFalse(d.union("a", "b"))
        self.assertFalse(d.union("b", "a"))
        self.assertEqual(d.size("a"), 2)
        self.assertEqual(d.group_count(), 2)

    def test_members_returns_independent_copy(self):
        d = build(3, list("abc"))
        d.union("a", "b")
        snap = d.members("a")
        snap.append("z")
        self.assertEqual(d.members("a"), ["a", "b"])

    def test_groups_returns_independent_copy(self):
        d = build(2, list("ab"))
        snap = d.groups()
        snap.append(["z"])
        self.assertEqual(d.groups(), [["a"], ["b"]])


class TestCheckpointAndRollback(unittest.TestCase):
    def test_rollback_to_start(self):
        d = build(4, list("abcd"))
        start = d.checkout()
        d.union("a", "b")
        d.union("c", "d")
        d.rollback(start)
        self.assertEqual(d.group_count(), 4)
        self.assertFalse(d.connected("a", "b"))
        self.assertFalse(d.connected("c", "d"))

    def test_rollback_to_middle(self):
        d = build(4, list("abcd"))
        d.checkout()
        d.union("a", "b")
        mid = d.checkout()
        d.union("c", "d")
        d.union("b", "c")
        d.rollback(mid)
        self.assertTrue(d.connected("a", "b"))
        self.assertFalse(d.connected("c", "d"))
        self.assertEqual(d.group_count(), 3)

    def test_union_after_rollback(self):
        d = build(4, list("abcd"))
        start = d.checkout()
        d.union("a", "b")
        d.rollback(start)
        d.union("c", "d")
        self.assertFalse(d.connected("a", "b"))
        self.assertTrue(d.connected("c", "d"))
        self.assertEqual(d.members("c"), ["c", "d"])

    def test_rollback_discards_later_checkpoints(self):
        d = build(3, list("abc"))
        first = d.checkout()
        d.union("a", "b")
        d.checkout()
        d.rollback(first)
        with self.assertRaises(NoCheckpointError):
            d.rollback(first + 1)

    def test_rollback_returns_self(self):
        d = build(2, list("ab"))
        point = d.checkout()
        self.assertIs(d.rollback(point), d)


class TestValidation(unittest.TestCase):
    def test_negative_size_rejected(self):
        with self.assertRaises(DsuInputError):
            build(-1)

    def test_label_count_mismatch_rejected(self):
        with self.assertRaises(DsuInputError):
            build(3, ["a", "b"])

    def test_empty_label_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, ["a", ""])

    def test_non_string_label_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, ["a", 7])

    def test_unknown_element_rejected(self):
        d = build(2, list("ab"))
        with self.assertRaises(UnknownElemError):
            d.size("zz")
        with self.assertRaises(UnknownElemError):
            d.connected("a", "zz")

    def test_bad_rollback_point_rejected(self):
        d = build(2, list("ab"))
        with self.assertRaises(NoCheckpointError):
            d.rollback(5)
        with self.assertRaises(NoCheckpointError):
            d.rollback(-1)

    def test_connected_on_empty_forest_rejected(self):
        d = build(0)
        with self.assertRaises(UnknownElemError):
            d.connected("a", "b")

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(DsuInputError, Erro))
        self.assertTrue(issubclass(UnknownElemError, Erro))
        self.assertTrue(issubclass(NoCheckpointError, Erro))


class TestDeterminism(unittest.TestCase):
    def test_fixed_input_repeatable(self):
        def run():
            d = build(6, list("abcdef"))
            point = d.checkout()
            d.union("a", "b")
            d.union("c", "d")
            d.union("b", "c")
            d.rollback(point)
            d.union("e", "f")
            return d.groups(), d.group_count(), d.size("e")

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
