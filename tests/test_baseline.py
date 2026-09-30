"""基线测试：锁住朴素实现的现状行为，实现升级后一字不许改且必须全绿。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hldquery import (  # noqa: E402
    PathQuerier,
    QueryError,
    InvalidNodeError,
    build_tree,
    chain_end_naive,
    step_count,
)

#          0
#        / | \
#       1  2  3
#      / \    |
#     4   5   6
PARENTS = [-1, 0, 0, 0, 1, 1, 3]
WEIGHTS = [3, 1, 4, 1, 5, 9, 2]


class TreeTest(unittest.TestCase):
    def test_build_shape(self):
        t = build_tree(7, PARENTS, WEIGHTS)
        self.assertEqual(t["n"], 7)
        self.assertEqual(t["parent"], PARENTS)
        self.assertEqual(t["children"][0], [1, 2, 3])
        self.assertEqual(t["children"][1], [4, 5])

    def test_build_rejects_bad_shape(self):
        with self.assertRaises(InvalidNodeError):
            build_tree(0, [], [])
        with self.assertRaises(InvalidNodeError):
            build_tree(3, [-1, 0], [1, 2, 3])

    def test_chain_end_naive(self):
        t = build_tree(7, PARENTS, WEIGHTS)
        self.assertEqual(chain_end_naive(t, 4), 4)
        self.assertEqual(chain_end_naive(t, 6), 3)
        self.assertEqual(chain_end_naive(t, 0), 0)


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.q = PathQuerier(7, PARENTS, WEIGHTS)

    def test_path_sum(self):
        self.assertEqual(self.q.path_sum(4, 5), 5 + 1 + 9)
        self.assertEqual(self.q.path_sum(4, 6), 5 + 1 + 3 + 1 + 2)
        self.assertEqual(self.q.path_sum(2, 2), 4)
        self.assertEqual(self.q.path_sum(0, 4), 3 + 1 + 5)

    def test_path_max(self):
        self.assertEqual(self.q.path_max(4, 5), 9)
        self.assertEqual(self.q.path_max(2, 6), 4)
        self.assertEqual(self.q.path_max(6, 6), 2)

    def test_subtree_sum(self):
        self.assertEqual(self.q.subtree_sum(0), sum(WEIGHTS))
        self.assertEqual(self.q.subtree_sum(1), 1 + 5 + 9)
        self.assertEqual(self.q.subtree_sum(4), 5)
        self.assertEqual(self.q.subtree_sum(3), 1 + 2)

    def test_update_changes_queries(self):
        self.q.update(5, 100)
        self.assertEqual(self.q.path_max(4, 5), 100)
        self.assertEqual(self.q.path_sum(1, 5), 1 + 100)
        self.assertEqual(self.q.subtree_sum(0), sum(WEIGHTS) - 9 + 100)

    def test_best_path(self):
        s, a, b = self.q.best_path()
        self.assertEqual(s, 4 + 3 + 1 + 9)  # 2-0-1-5
        self.assertEqual((a, b), (2, 5))

    def test_step_count_grows_with_depth(self):
        near = step_count(self.q, 0, 2)
        far = step_count(self.q, 4, 6)
        self.assertLess(near, far)
        self.assertEqual(far, 5)

    def test_walk_steps(self):
        self.assertEqual(self.q.walk_steps(4, 5), 2)
        self.assertEqual(self.q.walk_steps(4, 6), 4)
        self.assertEqual(self.q.walk_steps(0, 0), 0)

    def test_invalid_endpoint(self):
        with self.assertRaises(InvalidNodeError):
            self.q.path_sum(0, 7)
        with self.assertRaises(QueryError):
            self.q.subtree_sum(-1)


class DeterminismTest(unittest.TestCase):
    def test_repeatable(self):
        first = PathQuerier(7, PARENTS, WEIGHTS).best_path()
        second = PathQuerier(7, PARENTS, WEIGHTS).best_path()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
