"""NestedLoopJoin 现有行为的锁定测试。"""

import unittest

from joinlab.join import NestedLoopJoin


def by_first(row):
    return row[0]


class TestNestedLoopJoin(unittest.TestCase):
    def setUp(self):
        self.join = NestedLoopJoin()

    def test_simple_equi_join(self):
        left = [(1, "a"), (2, "b"), (3, "c")]
        right = [(2, "x"), (3, "y"), (4, "z")]
        result = self.join.join(left, right, by_first)
        self.assertEqual(
            result,
            [((2, "b"), (2, "x")), ((3, "c"), (3, "y"))],
        )

    def test_order_is_left_outer_right_inner(self):
        left = [(1, "a"), (2, "b")]
        right = [(2, "x"), (1, "y")]
        result = self.join.join(left, right, by_first)
        self.assertEqual(
            result,
            [((1, "a"), (1, "y")), ((2, "b"), (2, "x"))],
        )

    def test_duplicate_keys_produce_all_pairs(self):
        left = [(1, "a"), (1, "b")]
        right = [(1, "x"), (1, "y")]
        result = self.join.join(left, right, by_first)
        self.assertEqual(
            result,
            [
                ((1, "a"), (1, "x")),
                ((1, "a"), (1, "y")),
                ((1, "b"), (1, "x")),
                ((1, "b"), (1, "y")),
            ],
        )

    def test_right_key_can_differ(self):
        left = [(1, "a"), (2, "b")]
        right = [("id=2",), ("id=1",)]
        result = self.join.join(
            left, right, by_first, lambda row: int(row[0].split("=")[1])
        )
        self.assertEqual(
            result,
            [((1, "a"), ("id=1",)), ((2, "b"), ("id=2",))],
        )

    def test_no_match(self):
        left = [(1, "a")]
        right = [(9, "z")]
        self.assertEqual(self.join.join(left, right, by_first), [])

    def test_empty_tables(self):
        self.assertEqual(self.join.join([], [(1, "a")], by_first), [])
        self.assertEqual(self.join.join([(1, "a")], [], by_first), [])

    def test_does_not_modify_inputs(self):
        left = [(1, "a"), (2, "b")]
        right = [(2, "x")]
        left_copy = list(left)
        right_copy = list(right)
        self.join.join(left, right, by_first)
        self.assertEqual(left, left_copy)
        self.assertEqual(right, right_copy)

    def test_count_matches_join_length(self):
        left = [(1, "a"), (1, "b"), (2, "c")]
        right = [(1, "x"), (2, "y"), (2, "z")]
        self.assertEqual(self.join.count(left, right, by_first), 4)

    def test_keys_can_be_non_integer(self):
        left = [("k", 1), ("v", 2)]
        right = [("v", 9), ("k", 8)]
        result = self.join.join(left, right, by_first)
        self.assertEqual(result, [(("k", 1), ("k", 8)), (("v", 2), ("v", 9))])


if __name__ == "__main__":
    unittest.main()
