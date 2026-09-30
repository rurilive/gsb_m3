"""基线测试：锁住改造前 cdqx 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - counts_weak / counts_strict 对每个点扫全部点，逐个比对三维；
  - pairs_weak / pairs_strict 把每点的计数加起来；
  - order_by_axis 反复扫描剩余下标取最小值，两两枚举；
  - weighted_counts_weak / weighted_counts_strict 逐对累加被支配点的权值。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdqx.core import (  # noqa: E402
    CdqxErro,
    DominanceCounter,
    InputErro,
)


CHAIN = [(1, 1, 1), (2, 2, 2), (3, 3, 3)]


class TestConstructionBaseline(unittest.TestCase):
    def test_points_kept_in_order(self):
        self.assertEqual(DominanceCounter(CHAIN).points, tuple(CHAIN))

    def test_duplicates_kept(self):
        dc = DominanceCounter([(1, 1, 1), (1, 1, 1)])
        self.assertEqual(dc.points, ((1, 1, 1), (1, 1, 1)))

    def test_empty_allowed(self):
        self.assertEqual(DominanceCounter([]).points, ())

    def test_can_pass_iterator(self):
        dc = DominanceCounter(iter([(1, 2, 3)]))
        self.assertEqual(dc.points, ((1, 2, 3),))

    def test_default_weights_all_one(self):
        dc = DominanceCounter(CHAIN)
        self.assertEqual(dc.weights, (1, 1, 1))

    def test_weights_kept(self):
        dc = DominanceCounter(CHAIN, [4, 5, 6])
        self.assertEqual(dc.weights, (4, 5, 6))

    def test_none_points_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(None)

    def test_two_dims_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter([(1, 2)])

    def test_four_dims_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter([(1, 2, 3, 4)])

    def test_bool_attribute_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter([(True, 2, 3)])

    def test_float_attribute_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter([(1.5, 2, 3)])

    def test_weights_length_mismatch_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(CHAIN, [1, 2])

    def test_weights_none_means_default(self):
        # 显式给 None 是允许的，等价于默认权值全为一。
        self.assertEqual(DominanceCounter(CHAIN, None).weights, (1, 1, 1))

    def test_weights_bool_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(CHAIN, [1, True, 3])


class TestCountsBaseline(unittest.TestCase):
    def setUp(self):
        self.dc = DominanceCounter(CHAIN)

    def test_chain_weak_counts(self):
        self.assertEqual(self.dc.counts_weak(), (0, 1, 2))

    def test_chain_strict_counts(self):
        self.assertEqual(self.dc.counts_strict(), (0, 1, 2))

    def test_duplicate_splits_calibres(self):
        dc = DominanceCounter([(1, 1, 1), (1, 1, 1)])
        self.assertEqual(dc.counts_weak(), (1, 1))
        self.assertEqual(dc.counts_strict(), (0, 0))

    def test_negative_attributes_allowed(self):
        dc = DominanceCounter([(-5, -5, -5), (0, 0, 0)])
        self.assertEqual(dc.counts_weak(), (0, 1))

    def test_unsorted_by_axis(self):
        dc = DominanceCounter([(3, 3, 3), (1, 1, 1), (2, 2, 2)])
        self.assertEqual(dc.counts_weak(), (2, 0, 1))

    def test_empty_counts_empty(self):
        self.assertEqual(DominanceCounter([]).counts_weak(), ())

    def test_single_point_zero(self):
        self.assertEqual(DominanceCounter([(7, 8, 9)]).counts_weak(), (0,))

    def test_all_same_mutual_weak(self):
        dc = DominanceCounter([(2, 2, 2)] * 3)
        self.assertEqual(dc.counts_weak(), (2, 2, 2))
        self.assertEqual(dc.counts_strict(), (0, 0, 0))


class TestPairsBaseline(unittest.TestCase):
    def test_chain_pairs_weak(self):
        self.assertEqual(DominanceCounter(CHAIN).pairs_weak(), 3)

    def test_chain_pairs_strict(self):
        self.assertEqual(DominanceCounter(CHAIN).pairs_strict(), 3)

    def test_duplicate_pairs_weak(self):
        self.assertEqual(DominanceCounter([(1, 1, 1), (1, 1, 1)]).pairs_weak(), 2)

    def test_duplicate_pairs_strict(self):
        self.assertEqual(DominanceCounter([(1, 1, 1), (1, 1, 1)]).pairs_strict(), 0)

    def test_empty_pairs_zero(self):
        self.assertEqual(DominanceCounter([]).pairs_weak(), 0)
        self.assertEqual(DominanceCounter([]).pairs_strict(), 0)


class TestOrderBaseline(unittest.TestCase):
    def test_order_by_first_axis(self):
        dc = DominanceCounter([(3, 0, 0), (1, 0, 0), (2, 0, 0)])
        self.assertEqual(dc.order_by_axis(0), (1, 2, 0))

    def test_order_by_second_axis(self):
        dc = DominanceCounter([(0, 3, 0), (0, 1, 0), (0, 2, 0)])
        self.assertEqual(dc.order_by_axis(1), (1, 2, 0))

    def test_order_stable_on_ties(self):
        dc = DominanceCounter([(1, 5, 0), (1, 0, 0), (1, 9, 0)])
        self.assertEqual(dc.order_by_axis(0), (0, 1, 2))

    def test_order_empty(self):
        self.assertEqual(DominanceCounter([]).order_by_axis(0), ())

    def test_axis_out_of_range_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(CHAIN).order_by_axis(3)

    def test_axis_negative_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(CHAIN).order_by_axis(-1)

    def test_axis_bool_raises(self):
        with self.assertRaises(InputErro):
            DominanceCounter(CHAIN).order_by_axis(True)


class TestWeightedBaseline(unittest.TestCase):
    def test_weighted_weak(self):
        dc = DominanceCounter(CHAIN, [1, 2, 3])
        self.assertEqual(dc.weighted_counts_weak(), (0, 1, 3))

    def test_weighted_strict(self):
        dc = DominanceCounter(CHAIN, [1, 2, 3])
        self.assertEqual(dc.weighted_counts_strict(), (0, 1, 3))

    def test_weighted_big_integers(self):
        big = 10 ** 30
        dc = DominanceCounter(CHAIN, [big, 1, 1])
        self.assertEqual(dc.weighted_counts_weak(), (0, big, big + 1))

    def test_weighted_duplicates_strict_zero(self):
        dc = DominanceCounter([(1, 1, 1), (1, 1, 1)], [5, 7])
        self.assertEqual(dc.weighted_counts_strict(), (0, 0))

    def test_weighted_empty(self):
        self.assertEqual(DominanceCounter([], []).weighted_counts_weak(), ())


class TestScaleBaseline(unittest.TestCase):
    def test_comparison_counter_is_quadratic(self):
        dc = DominanceCounter(CHAIN)
        dc.counts_weak()
        self.assertEqual(dc.last_naive_comparisons, 9)

    def test_bit_probe_counter_zero_on_baseline(self):
        dc = DominanceCounter(CHAIN)
        dc.counts_weak()
        self.assertEqual(dc.last_bit_probe_count, 0)

    def test_counters_reset_per_call(self):
        dc = DominanceCounter(CHAIN)
        dc.counts_weak()
        first = dc.last_naive_comparisons
        dc.counts_weak()
        self.assertEqual(dc.last_naive_comparisons, first)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = DominanceCounter(CHAIN, [1, 2, 3])
        b = DominanceCounter(CHAIN, [1, 2, 3])
        self.assertEqual(a.counts_weak(), b.counts_weak())
        self.assertEqual(a.weighted_counts_weak(), b.weighted_counts_weak())

    def test_no_shared_state_across_instances(self):
        a = DominanceCounter([(1, 1, 1)])
        b = DominanceCounter([(9, 9, 9)])
        a.counts_weak()
        b.counts_weak()
        self.assertNotEqual(a.points, b.points)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(InputErro, CdqxErro))
        self.assertTrue(issubclass(CdqxErro, Exception))


if __name__ == "__main__":
    unittest.main()
