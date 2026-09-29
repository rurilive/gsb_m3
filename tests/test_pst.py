"""FlatCtl 现状行为的锁定测试（改造前基线，不许改）。

这些用例锁住改造前朴素实现的事实：整体拷贝、线性查询、整份快照。
改造后新行为另开 tests/test_persistent_seg.py，本文件保持一字不动。
"""

import unittest

from pseg import FlatCtl, PstError, PstIndexError


class TestConstruction(unittest.TestCase):
    def test_size_and_len(self):
        c = FlatCtl(8)
        self.assertEqual(c.size, 8)
        self.assertEqual(len(c), 8)

    def test_all_zero_initially(self):
        c = FlatCtl(5)
        self.assertEqual(c.values(), [0, 0, 0, 0, 0])

    def test_max_value_defaults_to_size(self):
        self.assertEqual(FlatCtl(7).max_value, 7)

    def test_max_value_explicit(self):
        self.assertEqual(FlatCtl(4, 100).max_value, 100)

    def test_negative_size_raises(self):
        with self.assertRaises(PstError):
            FlatCtl(-1)

    def test_empty_allowed(self):
        c = FlatCtl(0)
        self.assertEqual(len(c), 0)
        self.assertEqual(c.values(), [])


class TestAdd(unittest.TestCase):
    def test_add_returns_copy(self):
        c = FlatCtl(4)
        out = c.add(1, 5)
        self.assertEqual(out, [0, 5, 0, 0])
        self.assertEqual(c.values(), [0, 5, 0, 0])

    def test_returned_copy_is_independent(self):
        c = FlatCtl(3)
        out = c.add(0, 1)
        out[0] = 999
        self.assertEqual(c.values(), [1, 0, 0])

    def test_add_accumulates(self):
        c = FlatCtl(3)
        c.add(2, 4)
        c.add(2, 3)
        self.assertEqual(c.point(2), 7)

    def test_add_negative_delta(self):
        c = FlatCtl(3)
        c.add(1, 10)
        c.add(1, -4)
        self.assertEqual(c.point(1), 6)

    def test_add_at_edges(self):
        c = FlatCtl(3)
        c.add(0, 1)
        c.add(2, 2)
        self.assertEqual(c.values(), [1, 0, 2])

    def test_add_bad_index_raises(self):
        c = FlatCtl(3)
        with self.assertRaises(PstIndexError):
            c.add(3, 1)
        with self.assertRaises(PstIndexError):
            c.add(-1, 1)

    def test_index_error_is_pst_error(self):
        self.assertTrue(issubclass(PstIndexError, PstError))

    def test_catches_bad_index_as_base(self):
        with self.assertRaises(PstError):
            FlatCtl(2).add(9, 1)


class TestSnapshot(unittest.TestCase):
    def test_initial_version_count(self):
        self.assertEqual(FlatCtl(3).version_count(), 1)

    def test_snapshot_returns_version_id(self):
        c = FlatCtl(3)
        # 构造时已存入版本 0，故首次显式存快照得到版本 1。
        self.assertEqual(c.snapshot(), 1)
        self.assertEqual(c.snapshot(), 2)

    def test_version_count_grows(self):
        c = FlatCtl(3)
        c.snapshot()
        c.snapshot()
        self.assertEqual(c.version_count(), 3)

    def test_historical_version_kept(self):
        c = FlatCtl(3)
        c.add(0, 7)
        v = c.snapshot()
        c.add(0, 5)
        self.assertEqual(c.point(0, v), 7)
        self.assertEqual(c.point(0), 12)

    def test_snapshot_isolated_from_later_updates(self):
        c = FlatCtl(3)
        v = c.snapshot()
        c.add(1, 9)
        self.assertEqual(c.point(1, v), 0)

    def test_point_default_version_is_current(self):
        c = FlatCtl(3)
        c.add(2, 3)
        self.assertEqual(c.point(2), 3)

    def test_point_bad_version_raises(self):
        c = FlatCtl(3)
        with self.assertRaises(PstError):
            c.point(0, 5)

    def test_point_bad_index_raises(self):
        with self.assertRaises(PstIndexError):
            FlatCtl(3).point(4)


class TestCountLe(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(FlatCtl(0).count_le(5), 0)

    def test_all_zero(self):
        self.assertEqual(FlatCtl(4).count_le(0), 4)

    def test_mixed(self):
        c = FlatCtl(5)
        c.add(0, 1)
        c.add(1, 3)
        c.add(2, 3)
        c.add(3, 7)
        # 取值为 [1, 3, 3, 7, 0]，不大于 3 的位置有 4 个。
        self.assertEqual(c.count_le(3), 4)
        self.assertEqual(c.count_le(0), 1)
        self.assertEqual(c.count_le(100), 5)

    def test_threshold_below_all(self):
        c = FlatCtl(3)
        c.add(0, 2)
        self.assertEqual(c.count_le(1), 2)


class TestKthGe(unittest.TestCase):
    def test_first_hit(self):
        c = FlatCtl(5)
        c.add(2, 9)
        self.assertEqual(c.kth_ge(9), 2)

    def test_threshold_low_returns_zero(self):
        self.assertEqual(FlatCtl(3).kth_ge(0), 0)

    def test_no_hit_returns_minus_one(self):
        c = FlatCtl(3)
        c.add(0, 1)
        self.assertEqual(c.kth_ge(5), -1)

    def test_scans_left_to_right(self):
        c = FlatCtl(4)
        c.add(3, 2)
        c.add(1, 8)
        self.assertEqual(c.kth_ge(2), 1)


class TestDeterminism(unittest.TestCase):
    def test_fixed_sequence_repeats(self):
        def run():
            c = FlatCtl(6)
            c.add(0, 2)
            c.add(3, 5)
            v = c.snapshot()
            c.add(3, 1)
            return c.values(), c.point(3, v), c.count_le(2), c.kth_ge(5)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
