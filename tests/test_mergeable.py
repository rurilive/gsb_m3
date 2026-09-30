"""基线测试：锁住改造前 mergeseq.mergeable.MergeSeq 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - set 把当前序列整份复制一份，旧版本那条原样保留；
  - range_sum 拿序列从头扫过区间逐步累加，range_min/range_max 逐步比较；
  - kth_smallest 切片后整段排序再取下标；
  - 任何区间查询都在原序列上从头重扫，连续查同一段时扫描计数反复增长；
  - 非法版本、越界下标、空序列上的极值分别抛对应异常，且都继承基类；
  - 同一个实例反复调用不残留痕迹，固定输入重复跑结果一致。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mergeseq.mergeable import (  # noqa: E402
    EmptySeqError,
    IndexRangeError,
    MergeableSegError,
    MergeSeq,
    VersionError,
)


class TestBaselineQueries(unittest.TestCase):
    def setUp(self):
        self.s = MergeSeq([3, 1, 4, 1, 5, 9, 2, 6])

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
        s = MergeSeq([10, 20, 30])
        v1 = s.set(1, 99)
        self.assertEqual(v1, 1)
        self.assertEqual(s.get(1), 99)
        # 旧版本一字未改
        self.assertEqual(s.get(1, version=0), 20)
        self.assertEqual(s.values(version=0), [10, 20, 30])

    def test_consecutive_modifications_chain(self):
        s = MergeSeq([1, 2, 3, 4])
        v1 = s.set(0, 5)
        v2 = s.set(3, 8)
        v3 = s.set(1, 7)
        self.assertEqual((v1, v2, v3), (1, 2, 3))
        self.assertEqual(s.values(version=0), [1, 2, 3, 4])
        self.assertEqual(s.values(version=1), [5, 2, 3, 4])
        self.assertEqual(s.values(version=2), [5, 2, 3, 8])
        self.assertEqual(s.values(version=3), [5, 7, 3, 8])

    def test_query_old_version(self):
        s = MergeSeq([1, 2, 3, 4, 5])
        s.set(2, 100)
        self.assertEqual(s.range_sum(0, 5, version=0), 15)
        self.assertEqual(s.range_sum(0, 5, version=1), 112)
        self.assertEqual(s.range_max(0, 4, version=0), 5)
        self.assertEqual(s.range_max(0, 4, version=1), 100)

    def test_use_switches_current_version(self):
        s = MergeSeq([1, 2, 3])
        s.set(0, 9)
        self.assertEqual(s.version(), 1)
        self.assertEqual(s.use(0), 0)
        self.assertEqual(s.get(0), 1)

    def test_naive_copies_are_independent(self):
        # 基线每次整份复制：版本之间不共享底层数组
        s = MergeSeq([1, 2, 3])
        s.set(0, 7)
        self.assertIsNot(s._versions[0], s._versions[1])


class TestNaiveRescan(unittest.TestCase):
    def test_query_scans_whole_span(self):
        s = MergeSeq([0, 0, 0, 0, 0])
        # [1, 4) 覆盖三个位置，逐项累加即扫描三次
        self.assertEqual(s.range_sum(1, 4), 0)
        self.assertEqual(s.taken(), 3)

    def test_repeated_query_keeps_rescanning(self):
        s = MergeSeq([1, 2, 3, 4])
        before = s.taken()
        s.range_sum(0, 4)
        once = s.taken()
        s.range_sum(0, 4)
        twice = s.taken()
        # 零复用：同一段每查一次就重扫一遍，计数单调增长
        self.assertEqual(once - before, 4)
        self.assertEqual(twice - once, 4)

    def test_stats_reports_scans_and_live_values(self):
        s = MergeSeq([0, 0, 0, 0])
        s.set(0, 1)
        s.set(1, 2)
        st = s.stats()
        self.assertEqual(st["versions"], 3)
        self.assertEqual(st["size"], 4)
        # 朴素留痕：三个版本各存一份整数组
        self.assertEqual(st["live_values"], 12)

    def test_stats_is_fresh_dict(self):
        s = MergeSeq([1, 2])
        st = s.stats()
        st["versions"] = 999
        self.assertEqual(s.stats()["versions"], 1)


class TestBaselineEdges(unittest.TestCase):
    def test_empty_sequence(self):
        s = MergeSeq([])
        self.assertEqual(s.size(), 0)
        self.assertEqual(s.range_sum(0, 0), 0)
        with self.assertRaises(EmptySeqError):
            s.range_min(0, 0)

    def test_single_element(self):
        s = MergeSeq([42])
        self.assertEqual(s.range_sum(0, 1), 42)
        self.assertEqual(s.range_min(0, 0), 42)
        self.assertEqual(s.kth_smallest(0, 0, 1), 42)


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (VersionError, IndexRangeError, EmptySeqError):
            self.assertTrue(issubclass(exc, MergeableSegError))

    def test_bad_version_rejected(self):
        s = MergeSeq([1, 2, 3])
        with self.assertRaises(VersionError):
            s.get(0, version=5)
        with self.assertRaises(VersionError):
            s.use(-1)
        with self.assertRaises(VersionError):
            s.range_sum(0, 1, version=2)

    def test_out_of_range_index_rejected(self):
        s = MergeSeq([1, 2, 3])
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
        s = MergeSeq([1, 2, 3])
        with self.assertRaises(MergeableSegError):
            s.set(0, "x")


class TestBaselineDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        def run():
            s = MergeSeq([5, 3, 8, 1])
            s.set(1, 0)
            s.set(3, 9)
            return (s.range_sum(0, 4, version=1),
                    s.range_min(0, 3, version=2),
                    s.kth_smallest(0, 3, 2, version=0),
                    s.stats())

        self.assertEqual(run(), run())

    def test_no_cross_call_residue(self):
        s = MergeSeq([1, 2, 3])
        first = s.range_sum(0, 3)
        second = s.range_sum(0, 3)
        self.assertEqual(first, second)
        self.assertEqual(s.version(), 0)


if __name__ == "__main__":
    unittest.main()
