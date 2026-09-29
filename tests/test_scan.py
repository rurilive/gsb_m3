"""RangeSet 现有朴素行为的锁定测试。"""

import unittest

from rangetree.set import Interval, RangeSet


def sample():
    rs = RangeSet()
    rs.insert(1, 5)
    rs.insert(3, 8)
    rs.insert(10, 12)
    return rs


class TestInterval(unittest.TestCase):
    def test_fields(self):
        iv = Interval(2, 7)
        self.assertEqual((iv.left, iv.right), (2, 7))

    def test_degenerate_is_allowed(self):
        iv = Interval(4, 4)
        self.assertEqual((iv.left, iv.right), (4, 4))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            Interval(9, 1)

    def test_equality_and_hash(self):
        self.assertEqual(Interval(1, 2), Interval(1, 2))
        self.assertEqual(hash(Interval(1, 2)), hash(Interval(1, 2)))
        self.assertNotEqual(Interval(1, 2), Interval(1, 3))


class TestRangeSetBasics(unittest.TestCase):
    def test_insert_returns_copy(self):
        rs = RangeSet()
        iv = rs.insert(1, 5)
        self.assertEqual(iv, Interval(1, 5))
        iv.right = 99
        self.assertEqual(rs.intervals()[0], Interval(1, 5))

    def test_count_and_len(self):
        rs = sample()
        self.assertEqual(rs.count(), 3)
        self.assertEqual(len(rs), 3)

    def test_intervals_keeps_insertion_order(self):
        rs = sample()
        self.assertEqual(
            rs.intervals(),
            [Interval(1, 5), Interval(3, 8), Interval(10, 12)],
        )

    def test_intervals_returns_copies(self):
        rs = sample()
        got = rs.intervals()
        got[0].left = 0
        self.assertEqual(rs.intervals()[0], Interval(1, 5))

    def test_insert_invalid_raises(self):
        rs = RangeSet()
        with self.assertRaises(ValueError):
            rs.insert(5, 4)


class TestScanPoint(unittest.TestCase):
    def test_hits(self):
        rs = sample()
        hit = rs.scan_point(4)
        self.assertEqual(hit, [Interval(1, 5), Interval(3, 8)])

    def test_keeps_insertion_order(self):
        rs = RangeSet()
        for a, b in ((10, 20), (1, 8), (5, 7)):
            rs.insert(a, b)
        hit = rs.scan_point(6)
        self.assertEqual(hit, [Interval(1, 8), Interval(5, 7)])

    def test_boundaries_are_inclusive(self):
        rs = sample()
        self.assertEqual(rs.scan_point(1), [Interval(1, 5)])
        self.assertEqual(rs.scan_point(5), [Interval(1, 5), Interval(3, 8)])
        self.assertEqual(rs.scan_point(12), [Interval(10, 12)])

    def test_empty_result(self):
        rs = sample()
        self.assertEqual(rs.scan_point(100), [])

    def test_returns_copies(self):
        rs = sample()
        hit = rs.scan_point(4)
        hit[0].left = 0
        self.assertEqual(rs.intervals()[0], Interval(1, 5))


class TestScanInterval(unittest.TestCase):
    def test_hits(self):
        rs = sample()
        hit = rs.scan_interval(7, 11)
        self.assertEqual(hit, [Interval(3, 8), Interval(10, 12)])

    def test_touching_at_boundary_counts(self):
        rs = sample()
        self.assertEqual(rs.scan_interval(5, 5), [Interval(1, 5), Interval(3, 8)])

    def test_empty_result(self):
        rs = sample()
        self.assertEqual(rs.scan_interval(20, 30), [])

    def test_invalid_query_raises(self):
        rs = sample()
        with self.assertRaises(ValueError):
            rs.scan_interval(9, 2)


class TestAccessCount(unittest.TestCase):
    def test_scan_point_counts_every_interval(self):
        rs = sample()
        rs.reset_access_count()
        rs.scan_point(4)
        self.assertEqual(rs.access_count, 3)

    def test_scan_interval_counts_every_interval(self):
        rs = sample()
        rs.reset_access_count()
        rs.scan_interval(7, 11)
        self.assertEqual(rs.access_count, 3)

    def test_access_count_accumulates(self):
        rs = sample()
        rs.reset_access_count()
        rs.scan_point(4)
        rs.scan_point(4)
        self.assertEqual(rs.access_count, 6)

    def test_reset_access_count(self):
        rs = sample()
        rs.scan_point(4)
        rs.reset_access_count()
        self.assertEqual(rs.access_count, 0)


class TestEmptySetup(unittest.TestCase):
    def test_empty_queries(self):
        rs = RangeSet()
        self.assertEqual(rs.count(), 0)
        self.assertEqual(rs.scan_point(0), [])
        self.assertEqual(rs.scan_interval(-5, 5), [])


if __name__ == "__main__":
    unittest.main()
