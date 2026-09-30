"""spanlab 现有行为的锁定测试（基线，一字不改）。

全部用固定序列与逐字断言，不依赖随机输入，保证可复现。
"""

import unittest

from spanlab import (
    InvalidInputError,
    SpanError,
    bounds_greater,
    bounds_smaller,
    count_brute_scans,
    count_subarrays_as_min,
    first_greater_left,
    first_greater_right,
    first_smaller_left,
    first_smaller_right,
    largest_rectangle,
    sum_of_subarray_maxs,
    sum_of_subarray_mins,
)

MIXED = [3, 1, 4, 1, 5, 9, 2, 6]


class TestSingleBounds(unittest.TestCase):
    def test_greater_left_on_mixed(self):
        got = [first_greater_left(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [-1, 0, -1, 2, -1, -1, 5, 5])

    def test_greater_right_on_mixed(self):
        got = [first_greater_right(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [2, 2, 4, 4, 5, -1, 7, -1])

    def test_smaller_left_on_mixed(self):
        got = [first_smaller_left(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [-1, -1, 1, -1, 3, 4, 3, 6])

    def test_smaller_right_on_mixed(self):
        got = [first_smaller_right(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [1, -1, 3, -1, 6, 6, -1, -1])

    def test_strict_comparison_ignores_equals(self):
        data = [2, 2, 2]
        self.assertEqual(first_greater_left(data, 2), -1)
        self.assertEqual(first_greater_right(data, 0), -1)
        self.assertEqual(first_smaller_left(data, 2), -1)
        self.assertEqual(first_smaller_right(data, 0), -1)


class TestPairedBounds(unittest.TestCase):
    def test_bounds_greater_matches_single(self):
        left, right = bounds_greater(MIXED)
        self.assertEqual(left, [first_greater_left(MIXED, i) for i in range(len(MIXED))])
        self.assertEqual(right, [first_greater_right(MIXED, i) for i in range(len(MIXED))])

    def test_bounds_smaller_matches_single(self):
        left, right = bounds_smaller(MIXED)
        self.assertEqual(left, [first_smaller_left(MIXED, i) for i in range(len(MIXED))])
        self.assertEqual(right, [first_smaller_right(MIXED, i) for i in range(len(MIXED))])

    def test_bounds_on_single_element(self):
        self.assertEqual(bounds_greater([7]), ([-1], [-1]))
        self.assertEqual(bounds_smaller([7]), ([-1], [-1]))

    def test_bounds_on_strictly_increasing(self):
        data = [1, 2, 3, 4]
        left, right = bounds_greater(data)
        self.assertEqual(left, [-1, -1, -1, -1])
        self.assertEqual(right, [1, 2, 3, -1])

    def test_bounds_on_strictly_decreasing(self):
        data = [4, 3, 2, 1]
        left, right = bounds_greater(data)
        self.assertEqual(left, [-1, 0, 1, 2])
        self.assertEqual(right, [-1, -1, -1, -1])


class TestDerivedAggregates(unittest.TestCase):
    def test_largest_rectangle_on_mixed(self):
        self.assertEqual(largest_rectangle(MIXED), 10)

    def test_largest_rectangle_on_equal(self):
        self.assertEqual(largest_rectangle([2, 2, 2, 2]), 8)

    def test_largest_rectangle_on_empty(self):
        self.assertEqual(largest_rectangle([]), 0)

    def test_sum_of_subarray_mins_on_mixed(self):
        self.assertEqual(sum_of_subarray_mins(MIXED), 68)

    def test_sum_of_subarray_maxs_on_mixed(self):
        # [1] 取 1，[2] 取 2，[1, 2] 取 2，合计 5。
        self.assertEqual(sum_of_subarray_maxs([1, 2]), 5)

    def test_count_subarrays_as_min_on_mixed(self):
        self.assertEqual(count_subarrays_as_min(MIXED), [1, 14, 1, 10, 2, 1, 6, 1])

    def test_count_subarrays_as_min_on_equal(self):
        # 左侧严格大于、右侧大于等于，每个等值段只有最右那个拿到整段宽度。
        self.assertEqual(count_subarrays_as_min([5, 5, 5]), [3, 2, 1])


class TestInstrumentation(unittest.TestCase):
    def test_brute_scan_count_on_three(self):
        self.assertEqual(count_brute_scans([1, 2, 3]), 5)

    def test_brute_scan_count_grows_with_length(self):
        small = count_brute_scans(list(range(8)))
        large = count_brute_scans(list(range(32)))
        self.assertGreater(large, small)


class TestValidation(unittest.TestCase):
    def test_non_integer_raises(self):
        with self.assertRaises(InvalidInputError):
            first_greater_left([1, "x"], 0)

    def test_bool_is_not_integer(self):
        with self.assertRaises(InvalidInputError):
            bounds_greater([True, False])

    def test_bad_index_raises(self):
        with self.assertRaises(InvalidInputError):
            first_smaller_right([1, 2], 5)

    def test_negative_index_raises(self):
        with self.assertRaises(InvalidInputError):
            first_smaller_left([1, 2], -1)

    def test_errors_share_base_class(self):
        with self.assertRaises(SpanError):
            bounds_smaller([1.5])


if __name__ == "__main__":
    unittest.main()
