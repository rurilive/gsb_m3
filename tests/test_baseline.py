"""Heap 优先队列现有行为的锁定测试（基线，一字不改）。"""

import unittest

from leftistheap import (
    Heap,
    HeapError,
    LeftistHeapError,
    OperationError,
    build_heap,
    heap_sort,
    merge_heaps,
    merge_many,
    naive_merge_insert_count,
)
from leftistheap.builders import (
    ascending,
    constant,
    descending,
    empty_heap,
    from_values,
    single_heap,
    two_heaps,
    with_negative,
)


class TestConstruction(unittest.TestCase):
    def test_empty_heap(self):
        h = Heap()
        self.assertEqual(h.size, 0)
        self.assertTrue(h.is_empty())

    def test_build_from_values(self):
        h = build_heap([5, 1, 4, 2, 3])
        self.assertEqual(h.size, 5)
        self.assertFalse(h.is_empty())

    def test_from_values_builder(self):
        self.assertEqual(from_values([3, 1, 2]).to_sorted_list(), [1, 2, 3])

    def test_single_and_empty_builders(self):
        self.assertEqual(single_heap(9).peek_min(), 9)
        self.assertTrue(empty_heap().is_empty())

    def test_non_number_rejected(self):
        h = Heap()
        with self.assertRaises(HeapError):
            h.insert("x")

    def test_bool_is_not_a_number(self):
        with self.assertRaises(HeapError):
            build_heap([1, True])


class TestMinOperations(unittest.TestCase):
    def test_peek_min(self):
        self.assertEqual(build_heap([7, 3, 9]).peek_min(), 3)

    def test_peek_does_not_remove(self):
        h = build_heap([7, 3, 9])
        h.peek_min()
        self.assertEqual(h.size, 3)

    def test_pop_min_order(self):
        h = build_heap([5, 1, 4, 2, 3])
        self.assertEqual([h.pop_min() for _ in range(5)], [1, 2, 3, 4, 5])

    def test_peek_on_empty_raises(self):
        with self.assertRaises(OperationError):
            Heap().peek_min()

    def test_pop_on_empty_raises(self):
        with self.assertRaises(OperationError):
            Heap().pop_min()

    def test_insert_keeps_sorted(self):
        h = build_heap([5, 1, 4])
        h.insert(0)
        h.insert(9)
        self.assertEqual(h.to_sorted_list(), [0, 1, 4, 5, 9])

    def test_duplicates_allowed(self):
        h = build_heap([2, 2, 1, 1])
        self.assertEqual(h.to_sorted_list(), [1, 1, 2, 2])

    def test_negative_values(self):
        self.assertEqual(with_negative([3, -1, -7, 2]).peek_min(), -7)

    def test_drain_empties_heap(self):
        h = build_heap([4, 2, 6])
        self.assertEqual(h.drain(), [2, 4, 6])
        self.assertTrue(h.is_empty())


class TestMerge(unittest.TestCase):
    def test_merge_result_sorted(self):
        merged = merge_heaps(build_heap([1, 3, 5]), build_heap([2, 4, 6]))
        self.assertEqual(merged.to_sorted_list(), [1, 2, 3, 4, 5, 6])

    def test_merge_min_is_smallest(self):
        merged = merge_heaps(build_heap([1, 3, 5]), build_heap([2, 4, 6]))
        self.assertEqual(merged.peek_min(), 1)

    def test_merge_does_not_mutate_inputs(self):
        a = build_heap([1, 3, 5])
        b = build_heap([2, 4, 6])
        merge_heaps(a, b)
        self.assertEqual(a.to_sorted_list(), [1, 3, 5])
        self.assertEqual(b.to_sorted_list(), [2, 4, 6])

    def test_merge_with_empty_left(self):
        merged = merge_heaps(Heap(), build_heap([2, 1]))
        self.assertEqual(merged.to_sorted_list(), [1, 2])

    def test_merge_with_empty_right(self):
        merged = merge_heaps(build_heap([2, 1]), Heap())
        self.assertEqual(merged.to_sorted_list(), [1, 2])

    def test_merge_two_empties(self):
        merged = merge_heaps(Heap(), Heap())
        self.assertTrue(merged.is_empty())

    def test_merge_many(self):
        many = merge_many([build_heap([3, 1]), build_heap([9, 7]), build_heap([5, 0])])
        self.assertEqual(many.drain(), [0, 1, 3, 5, 7, 9])

    def test_merge_many_empty_list(self):
        self.assertTrue(merge_many([]).is_empty())

    def test_merge_bad_argument(self):
        with self.assertRaises(HeapError):
            merge_heaps(build_heap([1]), [1, 2])

    def test_two_heaps_builder(self):
        odd, even = two_heaps()
        self.assertEqual(odd.to_sorted_list(), [1, 3, 5, 7, 9])
        self.assertEqual(even.to_sorted_list(), [2, 4, 6, 8, 10])


class TestSortAndScale(unittest.TestCase):
    def test_heap_sort(self):
        self.assertEqual(heap_sort([5, 3, 9, 1, 7, 3]), [1, 3, 3, 5, 7, 9])

    def test_heap_sort_empty(self):
        self.assertEqual(heap_sort([]), [])

    def test_ascending_builder(self):
        self.assertEqual(ascending(6).to_sorted_list(), [0, 1, 2, 3, 4, 5])

    def test_descending_builder(self):
        self.assertEqual(descending(4).to_sorted_list(), [0, 1, 2, 3])

    def test_constant_builder(self):
        h = constant(5, 4)
        self.assertEqual(h.size, 5)
        self.assertEqual(h.to_sorted_list(), [4, 4, 4, 4, 4])

    def test_naive_merge_insert_count(self):
        odd, even = two_heaps()
        self.assertEqual(naive_merge_insert_count(odd, even), 35)

    def test_naive_count_with_empty(self):
        self.assertEqual(naive_merge_insert_count(Heap(), build_heap([1, 2])), 1)
        self.assertEqual(naive_merge_insert_count(build_heap([1, 2]), Heap()), 0)


class TestErrorHierarchy(unittest.TestCase):
    def test_subclasses(self):
        self.assertTrue(issubclass(HeapError, LeftistHeapError))
        self.assertTrue(issubclass(OperationError, LeftistHeapError))

    def test_base_of_exception(self):
        self.assertTrue(issubclass(LeftistHeapError, Exception))


if __name__ == "__main__":
    unittest.main()
