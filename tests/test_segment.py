"""基线测试：锁住改造前 beatsx.segment.BeatsSeq 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - 区间取最小值逐元素比对改写，把落下的数值差一并返回；
  - 区间加与区间赋值逐元素推进，区间求和与区间最值切片后逐项计算；
  - 区间一律左闭右开，非法区间立刻报错；
  - 空序列或空区间上求极值抛 EmptySeqError，且都继承 SegmentError；
  - 同一个实例反复调用不残留痕迹，固定操作序列重复跑结果一致。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beatsx.segment import (  # noqa: E402
    BadRangeError,
    BadValueError,
    BeatsSeq,
    EmptySeqError,
    SegmentError,
)


class TestBaselineRangeChmin(unittest.TestCase):
    def test_chmin_lowers_over_upper(self):
        s = BeatsSeq([5, 1, 4, 9, 2])
        dropped = s.range_chmin(0, 5, 4)
        # 5 压到 4 落下 1，9 压到 4 落下 5，其余不动
        self.assertEqual(dropped, 6)
        self.assertEqual(s.values(), [4, 1, 4, 4, 2])

    def test_chmin_upper_above_all_is_noop(self):
        s = BeatsSeq([3, 1, 2])
        self.assertEqual(s.range_chmin(0, 3, 100), 0)
        self.assertEqual(s.values(), [3, 1, 2])

    def test_chmin_equal_to_max(self):
        s = BeatsSeq([3, 1, 2])
        self.assertEqual(s.range_chmin(0, 3, 3), 0)
        self.assertEqual(s.values(), [3, 1, 2])

    def test_chmin_smaller_than_all(self):
        s = BeatsSeq([3, 1, 2])
        dropped = s.range_chmin(0, 3, -1)
        self.assertEqual(dropped, (3 + 1) + (1 + 1) + (2 + 1))
        self.assertEqual(s.values(), [-1, -1, -1])

    def test_chmin_only_touches_span(self):
        s = BeatsSeq([9, 9, 9, 9])
        s.range_chmin(1, 3, 0)
        self.assertEqual(s.values(), [9, 0, 0, 9])


class TestBaselineUpdates(unittest.TestCase):
    def test_range_add(self):
        s = BeatsSeq([1, 2, 3, 4])
        op = s.range_add(1, 3, 10)
        self.assertEqual(op, 1)
        self.assertEqual(s.values(), [1, 12, 13, 4])

    def test_range_add_negative(self):
        s = BeatsSeq([1, 2, 3, 4])
        s.range_add(0, 2, -5)
        self.assertEqual(s.values(), [-4, -3, 3, 4])

    def test_range_assign(self):
        s = BeatsSeq([1, 2, 3, 4])
        op = s.range_assign(0, 3, 7)
        self.assertEqual(op, 1)
        self.assertEqual(s.values(), [7, 7, 7, 4])

    def test_op_count_advances(self):
        s = BeatsSeq([0, 0])
        self.assertEqual(s.op_count(), 0)
        s.range_add(0, 1, 1)
        s.range_assign(1, 2, 2)
        s.range_chmin(0, 2, 1)
        self.assertEqual(s.op_count(), 3)

    def test_values_is_a_copy(self):
        s = BeatsSeq([1, 2, 3])
        got = s.values()
        got[0] = 999
        self.assertEqual(s.values(), [1, 2, 3])


class TestBaselineQueries(unittest.TestCase):
    def test_range_sum_half_open(self):
        s = BeatsSeq([3, 1, 4, 1, 5])
        self.assertEqual(s.range_sum(1, 4), 1 + 4 + 1)
        self.assertEqual(s.range_sum(0, 0), 0)

    def test_range_qmin_qmax(self):
        s = BeatsSeq([3, 1, 4, 1, 5])
        self.assertEqual(s.range_qmin(0, 5), 1)
        self.assertEqual(s.range_qmax(0, 5), 5)
        self.assertEqual(s.range_qmin(3, 5), 1)
        self.assertEqual(s.range_qmax(3, 4), 1)

    def test_queries_after_updates(self):
        s = BeatsSeq([1, 2, 3, 4, 5])
        s.range_add(0, 5, 5)
        s.range_chmin(0, 5, 6)
        self.assertEqual(s.values(), [6, 6, 6, 6, 6])
        self.assertEqual(s.range_sum(0, 5), 30)


class TestBaselineEdges(unittest.TestCase):
    def test_empty_sequence(self):
        s = BeatsSeq([])
        self.assertEqual(len(s), 0)
        self.assertEqual(s.range_sum(0, 0), 0)
        with self.assertRaises(EmptySeqError):
            s.range_qmin(0, 0)
        with self.assertRaises(EmptySeqError):
            s.range_qmax(0, 0)

    def test_single_element(self):
        s = BeatsSeq([42])
        self.assertEqual(s.range_sum(0, 1), 42)
        self.assertEqual(s.range_qmin(0, 0 + 1), 42)
        s.range_chmin(0, 1, 10)
        self.assertEqual(s.values(), [10])

    def test_empty_span_extremum_rejected(self):
        s = BeatsSeq([1, 2, 3])
        with self.assertRaises(EmptySeqError):
            s.range_qmin(1, 1)
        with self.assertRaises(EmptySeqError):
            s.range_qmax(2, 2)


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (BadRangeError, BadValueError, EmptySeqError):
            self.assertTrue(issubclass(exc, SegmentError))

    def test_bad_range_rejected(self):
        s = BeatsSeq([1, 2, 3])
        for bad in ((0, 4), (-1, 2), (2, 1)):
            with self.assertRaises(BadRangeError):
                s.range_sum(bad[0], bad[1])
        with self.assertRaises(BadRangeError):
            s.range_chmin(2, 1, 0)
        with self.assertRaises(BadRangeError):
            s.range_add(0, 9, 1)
        with self.assertRaises(BadRangeError):
            s.range_assign(-1, 2, 1)

    def test_bad_value_type_rejected(self):
        s = BeatsSeq([1, 2, 3])
        with self.assertRaises(BadValueError):
            s.range_chmin(0, 2, "x")
        with self.assertRaises(BadValueError):
            s.range_add(0, 2, True)
        with self.assertRaises(BadValueError):
            s.range_assign(0, 2, 1.0)
        with self.assertRaises(BadValueError):
            BeatsSeq([1, "a"])


class TestBaselineDeterminism(unittest.TestCase):
    def _run(self):
        s = BeatsSeq([5, 3, 8, 1, 9, 2])
        s.range_chmin(0, 6, 4)
        s.range_add(1, 4, 3)
        s.range_assign(5, 6, 0)
        return (s.values(), s.range_sum(0, 6), s.range_qmin(0, 6),
                s.range_qmax(0, 6), s.op_count())

    def test_repeat_runs_identical(self):
        self.assertEqual(self._run(), self._run())

    def test_no_cross_call_residue(self):
        s = BeatsSeq([1, 2, 3])
        first = s.range_sum(0, 3)
        second = s.range_sum(0, 3)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
