"""朴素精确去重集合的锁定测试。

只覆盖当前实现已经具备的能力：加入与去重、精确个数、成员查询、并集
累积、重置、参数与键的校验。新增能力（寄存器草图、调和平均估计与
偏差修正、稀疏与稠密表示、可交换可结合的合并、内存有界、桶数校验）
另开测试文件，本文件一字不改。
"""

import unittest

from hllbox.naive import ExactSet


class TestAddAndCount(unittest.TestCase):
    def test_empty_count_is_zero(self):
        self.assertEqual(ExactSet().count(), 0)

    def test_add_increases_count(self):
        exact = ExactSet()
        exact.add("a")
        self.assertEqual(exact.count(), 1)

    def test_duplicate_add_does_not_change_count(self):
        exact = ExactSet()
        exact.add("a")
        exact.add("a")
        exact.add("a")
        self.assertEqual(exact.count(), 1)

    def test_add_many_counts_distinct(self):
        exact = ExactSet()
        exact.add_many(["a", "b", "a", "c", "b"])
        self.assertEqual(exact.count(), 3)

    def test_contains_reflects_membership(self):
        exact = ExactSet()
        exact.add("a")
        self.assertTrue(exact.contains("a"))
        self.assertFalse(exact.contains("nope"))


class TestValidation(unittest.TestCase):
    def test_add_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            ExactSet().add("")

    def test_add_rejects_non_str_key(self):
        with self.assertRaises(ValueError):
            ExactSet().add(123)

    def test_add_rejects_none(self):
        with self.assertRaises(ValueError):
            ExactSet().add(None)


class TestUnion(unittest.TestCase):
    def test_union_accumulates_distinct(self):
        left = ExactSet()
        left.add_many(["a", "b"])
        right = ExactSet()
        right.add_many(["b", "c"])
        left.union(right)
        self.assertEqual(left.count(), 3)
        self.assertTrue(left.contains("c"))

    def test_union_is_exact_and_idempotent(self):
        left = ExactSet()
        left.add("a")
        right = ExactSet()
        right.add("a")
        left.union(right)
        self.assertEqual(left.count(), 1)

    def test_union_rejects_non_set(self):
        with self.assertRaises(ValueError):
            ExactSet().union(["a", "b"])


class TestReset(unittest.TestCase):
    def test_reset_clears_everything(self):
        exact = ExactSet()
        exact.add_many(["a", "b"])
        exact.reset()
        self.assertEqual(exact.count(), 0)
        self.assertFalse(exact.contains("a"))


if __name__ == "__main__":
    unittest.main()
