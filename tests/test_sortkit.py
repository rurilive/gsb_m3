"""sortx 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：整数排序、非负整数排序、定点数排序、按自定义
键排序、取值统计、稳定判据、与内置排序的比对、边界与异常层级。改造时本文件
一个字都不许改，新行为一律另开测试文件。
"""

import unittest

from sortx.sortkit import (
    NotIntegerError,
    SortxError,
    UnstableResultError,
    ValueOutOfRangeError,
    compare_with_builtin,
    count_max,
    count_min,
    describe_family,
    fixed_sort,
    integer_sort,
    key_sort,
    max_value,
    nonnegative_sort,
    probe_kernel,
    sort_and_assert_stable,
)


class TestIntegerSort(unittest.TestCase):
    def test_sorted_ascending(self):
        self.assertEqual(integer_sort([3, 1, 2]), [1, 2, 3])

    def test_negatives(self):
        self.assertEqual(integer_sort([1, -5, 0, -2]), [-5, -2, 0, 1])

    def test_empty(self):
        self.assertEqual(integer_sort([]), [])

    def test_single(self):
        self.assertEqual(integer_sort([7]), [7])

    def test_already_sorted_kept(self):
        self.assertEqual(integer_sort([1, 2, 3]), [1, 2, 3])

    def test_all_equal(self):
        self.assertEqual(integer_sort([4, 4, 4, 4]), [4, 4, 4, 4])

    def test_does_not_mutate_input(self):
        data = [3, 1, 2]
        integer_sort(data)
        self.assertEqual(data, [3, 1, 2])

    def test_accepts_tuple(self):
        self.assertEqual(integer_sort((9, 8, 7)), [7, 8, 9])

    def test_non_integer_raises(self):
        with self.assertRaises(NotIntegerError):
            integer_sort([1, 2.5])

    def test_bool_is_not_integer(self):
        with self.assertRaises(NotIntegerError):
            integer_sort([1, True])

    def test_non_iterable_raises(self):
        with self.assertRaises(NotIntegerError):
            integer_sort(5)


class TestStabilityPath(unittest.TestCase):
    def test_stable_result_returned(self):
        self.assertEqual(sort_and_assert_stable([3, 1, 2]), [1, 2, 3])

    def test_stable_with_duplicates(self):
        self.assertEqual(sort_and_assert_stable([2, 1, 2, 1]), [1, 1, 2, 2])

    def test_stable_empty(self):
        self.assertEqual(sort_and_assert_stable([]), [])

    def test_unstable_detected(self):
        from sortx.sortkit import _stable_verdict
        with self.assertRaises(UnstableResultError):
            _stable_verdict([1, 1], [1, 0])


class TestNonnegativeSort(unittest.TestCase):
    def test_ascending(self):
        self.assertEqual(nonnegative_sort([5, 0, 3, 3]), [0, 3, 3, 5])

    def test_empty(self):
        self.assertEqual(nonnegative_sort([]), [])

    def test_zero_only(self):
        self.assertEqual(nonnegative_sort([0, 0]), [0, 0])

    def test_negative_raises(self):
        with self.assertRaises(ValueOutOfRangeError):
            nonnegative_sort([1, -1, 2])

    def test_small_range(self):
        self.assertEqual(nonnegative_sort([1, 0, 1, 0, 1]), [0, 0, 1, 1, 1])


class TestFixedSort(unittest.TestCase):
    def test_digits_zero_is_integer(self):
        self.assertEqual(fixed_sort([3, -1, 2], 0), [-1, 2, 3])

    def test_one_digit(self):
        self.assertEqual(fixed_sort([2.5, 1.25, 2.5], 2), [1.25, 2.5, 2.5])

    def test_negatives_with_digits(self):
        self.assertEqual(fixed_sort([-1.5, 0.0, 1.5], 1), [-1.5, 0.0, 1.5])

    def test_empty(self):
        self.assertEqual(fixed_sort([], 2), [])

    def test_bad_digits_raises(self):
        with self.assertRaises(NotIntegerError):
            fixed_sort([1, 2], -1)

    def test_mixed_int_and_float(self):
        self.assertEqual(fixed_sort([2, 1.5, 1, 1.25], 2),
                         [1, 1.25, 1.5, 2])

    def test_non_number_raises(self):
        with self.assertRaises(NotIntegerError):
            fixed_sort(["x"], 2)


class TestKeySort(unittest.TestCase):
    def test_by_second_field(self):
        data = [(1, "b"), (2, "a"), (3, "a")]
        self.assertEqual(key_sort(data, lambda pair: pair[1]),
                         [(2, "a"), (3, "a"), (1, "b")])

    def test_by_absolute_value(self):
        self.assertEqual(key_sort([-3, 1, -2], lambda x: abs(x)), [1, -2, -3])

    def test_empty(self):
        self.assertEqual(key_sort([], lambda x: x), [])

    def test_incomparable_key_raises(self):
        with self.assertRaises(ValueOutOfRangeError):
            key_sort([1, 2], lambda x: (1, "a" if x == 1 else 1))

    def test_string_key(self):
        self.assertEqual(key_sort(["bb", "a", "ccc"], len), ["a", "bb", "ccc"])


class TestCounting(unittest.TestCase):
    def test_count_max(self):
        self.assertEqual(count_max([3, 9, 1]), 9)

    def test_count_min(self):
        self.assertEqual(count_min([3, 9, 1]), 1)

    def test_count_empty_is_zero(self):
        self.assertEqual(count_max([]), 0)
        self.assertEqual(count_min([]), 0)

    def test_max_value_alias(self):
        self.assertEqual(max_value([-4, -9]), -4)

    def test_negatives_max(self):
        self.assertEqual(count_max([-4, -9, -1]), -1)


class TestCompareWithBuiltin(unittest.TestCase):
    def test_matches(self):
        result, same = compare_with_builtin([3, 1, 2, 1])
        self.assertEqual(result, [1, 1, 2, 3])
        self.assertTrue(same)

    def test_empty_matches(self):
        result, same = compare_with_builtin([])
        self.assertEqual(result, [])
        self.assertTrue(same)


class TestDescribeFamily(unittest.TestCase):
    def test_returns_list_of_names(self):
        names = describe_family()
        self.assertIsInstance(names, list)
        self.assertTrue(all(isinstance(name, str) for name in names))


class TestProbeDeterminism(unittest.TestCase):
    def test_repeated_probe_differs(self):
        data = [1, 2, 3]
        first = probe_kernel(data)
        second = probe_kernel(data)
        self.assertNotEqual(first, second)


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (NotIntegerError, ValueOutOfRangeError,
                    UnstableResultError):
            self.assertTrue(issubclass(exc, SortxError))

    def test_catchable_via_base(self):
        with self.assertRaises(SortxError):
            integer_sort(["x"])


if __name__ == "__main__":
    unittest.main()
