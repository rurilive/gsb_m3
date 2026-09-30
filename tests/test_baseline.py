"""可持久化数组现有行为的锁定测试（基线，一字不改）。"""

import unittest

from persist.parray import (
    BadArgument,
    Erro,
    IndexOutOfRange,
    KthOutOfRange,
    PersistentArray,
    VersionOutOfRange,
)


class TestBuild(unittest.TestCase):
    def test_empty_version_zero(self):
        arr = PersistentArray(4, 0)
        self.assertEqual(arr.version_count(), 1)
        self.assertEqual(arr.latest_version(), 0)
        for i in range(4):
            self.assertEqual(arr.query(0, i), 0)

    def test_fill_value(self):
        arr = PersistentArray(3, 7)
        self.assertEqual(arr.snapshot(0), (7, 7, 7))

    def test_zero_length(self):
        arr = PersistentArray(0, 5)
        self.assertEqual(arr.length, 0)
        self.assertEqual(arr.version_count(), 1)

    def test_rejects_negative_length(self):
        with self.assertRaises(BadArgument):
            PersistentArray(-1, 0)

    def test_rejects_non_integer_length(self):
        with self.assertRaises(BadArgument):
            PersistentArray(2.5, 0)


class TestModify(unittest.TestCase):
    def test_returns_new_version(self):
        arr = PersistentArray(3, 0)
        v1 = arr.modify(0, 1, 9)
        self.assertEqual(v1, 1)
        self.assertEqual(arr.version_count(), 2)

    def test_old_version_unchanged(self):
        arr = PersistentArray(3, 0)
        arr.modify(0, 1, 9)
        self.assertEqual(arr.query(0, 1), 0)
        self.assertEqual(arr.query(1, 1), 9)

    def test_chain_of_modifications(self):
        arr = PersistentArray(3, 0)
        v1 = arr.modify(0, 0, 1)
        v2 = arr.modify(v1, 0, 2)
        v3 = arr.modify(v2, 0, 3)
        self.assertEqual(arr.query(v1, 0), 1)
        self.assertEqual(arr.query(v2, 0), 2)
        self.assertEqual(arr.query(v3, 0), 3)

    def test_branch_from_old_version(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 1)
        v2 = arr.modify(v1, 1, 2)
        v3 = arr.modify(v1, 1, 5)
        self.assertEqual(arr.query(v2, 1), 2)
        self.assertEqual(arr.query(v3, 1), 5)
        self.assertEqual(arr.query(v3, 0), 1)

    def test_rejects_bad_version(self):
        arr = PersistentArray(2, 0)
        with self.assertRaises(VersionOutOfRange):
            arr.modify(1, 0, 1)

    def test_rejects_bad_index(self):
        arr = PersistentArray(2, 0)
        with self.assertRaises(IndexOutOfRange):
            arr.modify(0, 2, 1)

    def test_errors_share_base_class(self):
        arr = PersistentArray(2, 0)
        for exc in (VersionOutOfRange, IndexOutOfRange, BadArgument, KthOutOfRange):
            self.assertTrue(issubclass(exc, Erro))


class TestKth(unittest.TestCase):
    def test_single_write(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 8)
        self.assertEqual(arr.kth(0, v1, 1), 8)

    def test_third_smallest(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 5)
        v2 = arr.modify(v1, 0, 1)
        v3 = arr.modify(v2, 0, 3)
        self.assertEqual(arr.kth(0, v3, 1), 1)
        self.assertEqual(arr.kth(0, v3, 2), 3)
        self.assertEqual(arr.kth(0, v3, 3), 5)

    def test_sub_range(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 5)
        v2 = arr.modify(v1, 0, 1)
        v3 = arr.modify(v2, 0, 3)
        self.assertEqual(arr.kth(v1, v3, 1), 1)
        self.assertEqual(arr.kth(v1, v3, 2), 3)

    def test_empty_range(self):
        arr = PersistentArray(2, 0)
        arr.modify(0, 0, 5)
        with self.assertRaises(KthOutOfRange):
            arr.kth(0, 0, 1)

    def test_rejects_bad_k(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 5)
        with self.assertRaises(KthOutOfRange):
            arr.kth(0, v1, 2)

    def test_rejects_swapped_range(self):
        arr = PersistentArray(2, 0)
        v1 = arr.modify(0, 0, 5)
        with self.assertRaises(VersionOutOfRange):
            arr.kth(v1, 0, 1)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_is_tuple(self):
        arr = PersistentArray(3, 1)
        d = arr.modify(0, 0, 9)
        self.assertIsInstance(arr.snapshot(d), tuple)

    def test_rejects_bad_version(self):
        arr = PersistentArray(3, 1)
        with self.assertRaises(VersionOutOfRange):
            arr.snapshot(5)


if __name__ == "__main__":
    unittest.main()
