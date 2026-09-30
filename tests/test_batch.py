"""QueryBatch 现有行为的锁定测试。"""

import unittest

from offx.batch import QueryBatch, answer_queries, scan_visits


VALUES = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]


def sample():
    return QueryBatch(VALUES)


class TestBatchBasics(unittest.TestCase):
    def test_size(self):
        self.assertEqual(sample().size(), len(VALUES))

    def test_values_are_copied_on_construct(self):
        src = [1, 2, 3]
        b = QueryBatch(src)
        src[0] = 99
        self.assertEqual(b.range_sum(0, 0), 1)

    def test_scan_count_starts_at_zero_for_fresh_batch(self):
        self.assertEqual(QueryBatch([1, 2]).scan_count, 0)

    def test_reset_scan_count(self):
        b = sample()
        b.range_sum(0, 2)
        b.reset_scan_count()
        self.assertEqual(b.scan_count, 0)


class TestRangeSum(unittest.TestCase):
    def test_range_sum_full(self):
        self.assertEqual(sample().range_sum(0, 9), 39)

    def test_range_sum_middle(self):
        self.assertEqual(sample().range_sum(2, 5), 4 + 1 + 5 + 9)

    def test_range_sum_single_point(self):
        self.assertEqual(sample().range_sum(4, 4), 5)

    def test_range_sum_counts_every_position(self):
        b = sample()
        b.reset_scan_count()
        b.range_sum(3, 6)
        self.assertEqual(b.scan_count, 4)

    def test_range_sum_illegal_range(self):
        b = sample()
        with self.assertRaises(ValueError):
            b.range_sum(6, 3)
        with self.assertRaises(ValueError):
            b.range_sum(-1, 2)
        with self.assertRaises(ValueError):
            b.range_sum(0, len(VALUES))


class TestRangeDistinct(unittest.TestCase):
    def test_distinct_full(self):
        self.assertEqual(sample().range_distinct(0, 9), 7)

    def test_distinct_segment(self):
        self.assertEqual(sample().range_distinct(1, 4), 3)

    def test_distinct_single_point(self):
        self.assertEqual(sample().range_distinct(7, 7), 1)

    def test_distinct_counts_every_position(self):
        b = sample()
        b.reset_scan_count()
        b.range_distinct(0, 2)
        self.assertEqual(b.scan_count, 3)


class TestRangeCountClass(unittest.TestCase):
    def test_count_class(self):
        self.assertEqual(sample().range_count_class(1, 8, 5), 2)

    def test_count_class_absent(self):
        self.assertEqual(sample().range_count_class(0, 9, 100), 0)

    def test_count_class_single_point(self):
        self.assertEqual(sample().range_count_class(6, 6, 2), 1)


class TestAnswerQueries(unittest.TestCase):
    def test_answer_queries_sum(self):
        qs = [(0, 2), (4, 5), (7, 7)]
        self.assertEqual(answer_queries(VALUES, qs, "sum"), [8, 14, 6])

    def test_answer_queries_distinct(self):
        qs = [(0, 0), (0, 9)]
        self.assertEqual(answer_queries(VALUES, qs, "distinct"), [1, 7])

    def test_answer_queries_count_k(self):
        qs = [(0, 9, 5), (0, 3, 1)]
        self.assertEqual(answer_queries(VALUES, qs, "count_k"), [2, 2])

    def test_answer_queries_unknown_mode(self):
        with self.assertRaises(ValueError):
            answer_queries(VALUES, [(0, 1)], "median")

    def test_answer_queries_preserves_order(self):
        qs = [(2, 4), (0, 0), (9, 9)]
        self.assertEqual(answer_queries(VALUES, qs, "sum"), [10, 3, 3])

    def test_scan_visits_matches_bruteforce(self):
        qs = [(0, 2), (5, 9), (3, 3)]
        b = QueryBatch(VALUES)
        b.reset_scan_count()
        for q in qs:
            b.range_sum(q[0], q[1])
        self.assertEqual(b.scan_count, scan_visits(qs))

    def test_repeated_runs_are_identical(self):
        qs = [(1, 6), (0, 4), (4, 4)]
        first = answer_queries(VALUES, qs, "sum")
        second = answer_queries(VALUES, qs, "sum")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
