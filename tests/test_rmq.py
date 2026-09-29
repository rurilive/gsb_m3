"""NaiveRMQ 现状行为的锁定测试（改造前基线，不许改）。"""

import unittest

from rmqlib.rmq import NaiveRMQ


class TestBasics(unittest.TestCase):
    def test_length(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(len(q), 5)

    def test_value_at(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertEqual(q.value_at(0), 3)
        self.assertEqual(q.value_at(2), 4)

    def test_value_at_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(ValueError):
            q.value_at(3)
        with self.assertRaises(ValueError):
            q.value_at(-1)

    def test_as_list_is_a_copy(self):
        q = NaiveRMQ([3, 1, 4])
        snapshot = q.as_list()
        snapshot.append(99)
        self.assertEqual(q.as_list(), [3, 1, 4])

    def test_accepts_mixed_numeric_input(self):
        q = NaiveRMQ([True, 2, 0])
        self.assertEqual(q.as_list(), [1, 2, 0])


class TestQueryMin(unittest.TestCase):
    def test_single_element(self):
        q = NaiveRMQ([7])
        self.assertEqual(q.query_min(0, 1), 7)

    def test_full_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_min(0, 5), 1)

    def test_general_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_min(1, 3), 1)
        self.assertEqual(q.query_min(2, 5), 1)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_min(2, 2))

    def test_left_greater_right_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(ValueError):
            q.query_min(2, 1)

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(ValueError):
            q.query_min(0, 4)
        with self.assertRaises(ValueError):
            q.query_min(-1, 2)


class TestQueryMax(unittest.TestCase):
    def test_full_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_max(0, 5), 5)

    def test_general_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_max(0, 3), 4)
        self.assertEqual(q.query_max(3, 5), 5)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_max(1, 1))

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(ValueError):
            q.query_max(0, 5)


class TestQueryArgmin(unittest.TestCase):
    def test_returns_first_occurrence_index(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_argmin(0, 5), 1)
        self.assertEqual(q.query_argmin(1, 4), 1)

    def test_single_element(self):
        q = NaiveRMQ([9, 2, 7])
        self.assertEqual(q.query_argmin(1, 2), 1)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_argmin(0, 0))

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(ValueError):
            q.query_argmin(0, 4)


class TestQueryMany(unittest.TestCase):
    def test_batch_matches_single(self):
        q = NaiveRMQ([5, 2, 8, 1, 9, 3])
        ranges = [(0, 6), (0, 1), (1, 3), (2, 2), (4, 6)]
        self.assertEqual(q.query_many(ranges), [1, 5, 2, None, 3])

    def test_batch_empty(self):
        q = NaiveRMQ([1, 2, 3])
        self.assertEqual(q.query_many([]), [])


if __name__ == "__main__":
    unittest.main()
