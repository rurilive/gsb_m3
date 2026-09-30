"""基线测试：锁住改造前 persistx.pst.PersistSeq 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - set 每次把整个数组整份复制一份，旧版本那份原样保留；
  - range_sum 拿副本切片逐项累加，range_min/range_max 逐项取极值；
  - kth_smallest 切片后整段排序再取下标；
  - 非法版本、越界下标、空序列上的极值分别抛对应异常，且都继承 PstError；
  - 同一个实例反复调用不残留痕迹，固定输入重复跑结果一致。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistx.pst import (  # noqa: E402
    EmptySeqError,
    IndexRangeError,
    PersistSeq,
    PstError,
    VersionError,
)


class TestBaselineQueries(unittest.TestCase):
    def setUp(self):
        self.s = PersistSeq([3, 1, 4, 1, 5, 9, 2, 6])

    def test_size_and_get(self):
        self.assertEqual(self.s.size(), 8)
        self.assertEqual(self.s.get(0), 3)
        self.assertEqual(self.s.get(7), 6)

    def test_range_sum_is_half_open(self):
        # [1, 4) 对应下标 1、2、3 -> 1 + 4 + 1
        self.assertEqual(self.s.range_sum(1, 4), 6)
        self.assertEqual(self.s.range_sum(0, 0), 0)

    def test_range_min_max_are_closed(self):
        self.assertEqual(self.s.range_min(0, 7), 1)
        self.assertEqual(self.s.range_max(0, 7), 9)
        self.assertEqual(self.s.range_min(3, 4), 1)
        self.assertEqual(self.s.range_max(4, 5), 9)

    def test_kth_smallest(self):
        self.assertEqual(self.s.kth_smallest(0, 7, 1), 1)
        self.assertEqual(self.s.kth_smallest(0, 7, 8), 9)
        self.assertEqual(self.s.kth_smallest(4, 6, 1), 2)

    def test_values_is_a_copy(self):
        got = self.s.values()
        got[0] = 999
        self.assertEqual(self.s.get(0), 3)


class TestNaiveVersioning(unittest.TestCase):
    def test_set_returns_new_version_and_keeps_old(self):
        s = PersistSeq([10, 20, 30])
        v1 = s.set(1, 99)
        self.assertEqual(v1, 1)
        self.assertEqual(s.get(1), 99)
        # 旧版本一字未改
        self.assertEqual(s.get(1, version=0), 20)
        self.assertEqual(s.values(version=0), [10, 20, 30])

    def test_consecutive_modifications_chain(self):
        s = PersistSeq([1, 2, 3, 4])
        v1 = s.set(0, 5)
        v2 = s.set(3, 8)
        v3 = s.set(1, 7)
        self.assertEqual((v1, v2, v3), (1, 2, 3))
        self.assertEqual(s.values(version=0), [1, 2, 3, 4])
        self.assertEqual(s.values(version=1), [5, 2, 3, 4])
        self.assertEqual(s.values(version=2), [5, 2, 3, 8])
        self.assertEqual(s.values(version=3), [5, 7, 3, 8])

    def test_query_old_version(self):
        s = PersistSeq([1, 2, 3, 4, 5])
        s.set(2, 100)
        self.assertEqual(s.range_sum(0, 5, version=0), 15)
        self.assertEqual(s.range_sum(0, 5, version=1), 112)
        self.assertEqual(s.range_max(0, 4, version=0), 5)
        self.assertEqual(s.range_max(0, 4, version=1), 100)

    def test_use_switches_current_version(self):
        s = PersistSeq([1, 2, 3])
        s.set(0, 9)
        self.assertEqual(s.version(), 1)
        self.assertEqual(s.use(0), 0)
        self.assertEqual(s.get(0), 1)

    def test_naive_copies_are_independent(self):
        # 基线每次整份复制：版本之间不共享底层数组
        s = PersistSeq([1, 2, 3])
        s.set(0, 7)
        self.assertIsNot(s._versions[0], s._versions[1])


class TestNaiveFootprint(unittest.TestCase):
    def test_stats_counts_live_values(self):
        s = PersistSeq([0, 0, 0, 0])
        s.set(0, 1)
        s.set(1, 2)
        st = s.stats()
        self.assertEqual(st["versions"], 3)
        self.assertEqual(st["size"], 4)
        # 朴素留痕：三个版本各存一份整数组
        self.assertEqual(st["live_values"], 12)

    def test_stats_is_fresh_dict(self):
        s = PersistSeq([1, 2])
        st = s.stats()
        st["versions"] = 999
        self.assertEqual(s.stats()["versions"], 1)


class TestBaselineEdges(unittest.TestCase):
    def test_empty_sequence(self):
        s = PersistSeq([])
        self.assertEqual(s.size(), 0)
        self.assertEqual(s.range_sum(0, 0), 0)
        with self.assertRaises(EmptySeqError):
            s.range_min(0, 0)

    def test_single_element(self):
        s = PersistSeq([42])
        self.assertEqual(s.range_sum(0, 1), 42)
        self.assertEqual(s.range_min(0, 0), 42)
        self.assertEqual(s.kth_smallest(0, 0, 1), 42)


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (VersionError, IndexRangeError, EmptySeqError):
            self.assertTrue(issubclass(exc, PstError))

    def test_bad_version_rejected(self):
        s = PersistSeq([1, 2, 3])
        with self.assertRaises(VersionError):
            s.get(0, version=5)
        with self.assertRaises(VersionError):
            s.use(-1)
        with self.assertRaises(VersionError):
            s.range_sum(0, 1, version=2)

    def test_out_of_range_index_rejected(self):
        s = PersistSeq([1, 2, 3])
        with self.assertRaises(IndexRangeError):
            s.get(3)
        with self.assertRaises(IndexRangeError):
            s.set(-1, 0)
        with self.assertRaises(IndexRangeError):
            s.range_sum(0, 4)
        with self.assertRaises(IndexRangeError):
            s.range_min(2, 1)
        with self.assertRaises(IndexRangeError):
            s.kth_smallest(0, 2, 0)

    def test_bad_value_type_rejected(self):
        s = PersistSeq([1, 2, 3])
        with self.assertRaises(PstError):
            s.set(0, "x")


class TestBaselineDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        def run():
            s = PersistSeq([5, 3, 8, 1])
            s.set(1, 0)
            s.set(3, 9)
            return (s.range_sum(0, 4, version=1),
                    s.range_min(0, 3, version=2),
                    s.kth_smallest(0, 3, 2, version=0),
                    s.stats())

        self.assertEqual(run(), run())

    def test_no_cross_call_residue(self):
        s = PersistSeq([1, 2, 3])
        first = s.range_sum(0, 3)
        second = s.range_sum(0, 3)
        self.assertEqual(first, second)
        self.assertEqual(s.version(), 0)


if __name__ == "__main__":
    unittest.main()
