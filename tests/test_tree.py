"""FlatIntervals 现有行为的锁定测试。

这一套是基线：改造区间索引之后，这些用例必须仍然全绿、一个字都不改。
"""

import unittest

from intervalx.tree import FlatIntervals, IntervalError, InvalidInterval


class TestAddAndRemove(unittest.TestCase):
    def test_empty(self):
        f = FlatIntervals()
        self.assertEqual(len(f), 0)
        self.assertEqual(f.names(), [])
        self.assertEqual(f.intervals(), [])
        self.assertEqual(f.overlaps(0, 10), [])
        self.assertEqual(f.point_hit(3), [])
        self.assertEqual(f.merge_all(), [])

    def test_add_and_len(self):
        f = FlatIntervals()
        f.add(1, 5, "a")
        f.add(3, 8, "b")
        self.assertEqual(len(f), 2)
        self.assertIn("a", f)
        self.assertEqual(f.names(), ["a", "b"])
        self.assertEqual(f.intervals(), [(1, 5, "a"), (3, 8, "b")])

    def test_add_overwrites_same_name(self):
        f = FlatIntervals()
        f.add(1, 5, "a")
        f.add(2, 9, "a")
        self.assertEqual(len(f), 1)
        self.assertEqual(f.intervals(), [(2, 9, "a")])

    def test_add_bad_interval_raises(self):
        f = FlatIntervals()
        self.assertRaises(InvalidInterval, f.add, 5, 1, "bad")

    def test_remove(self):
        f = FlatIntervals()
        f.add(1, 5, "a")
        f.add(3, 8, "b")
        self.assertTrue(f.remove("a"))
        self.assertFalse(f.remove("a"))
        self.assertEqual(f.names(), ["b"])

    def test_invalid_add_is_interval_error(self):
        f = FlatIntervals()
        with self.assertRaises(IntervalError):
            f.add(9, 2, "x")


class TestOverlaps(unittest.TestCase):
    def setUp(self):
        self.f = FlatIntervals()
        self.f.add(1, 5, "a")
        self.f.add(4, 9, "b")
        self.f.add(10, 12, "c")

    def test_overlap_basic(self):
        self.assertEqual(self.f.overlaps(3, 6), ["a", "b"])
        self.assertEqual(self.f.overlaps(5, 10), ["b"])

    def test_touching_not_overlap(self):
        # 仅端点相接不算相交：a 的右端 5 与 b 的左端 4 已相交，
        # 而 c 的左端 10 与 b 的右端 9 相接，不得算相交。
        self.assertEqual(self.f.overlaps(9, 10), [])
        self.assertEqual(self.f.overlaps(5, 5), [])

    def test_overlap_none(self):
        self.assertEqual(self.f.overlaps(20, 30), [])

    def test_overlap_bad_interval_raises(self):
        self.assertRaises(InvalidInterval, self.f.overlaps, 5, 4)

    def test_overlap_degenerate(self):
        f = FlatIntervals()
        f.add(3, 3, "empty")
        f.add(2, 5, "solid")
        self.assertEqual(f.overlaps(3, 4), ["solid"])
        self.assertEqual(f.overlaps(3, 3), [])


class TestPointHit(unittest.TestCase):
    def setUp(self):
        self.f = FlatIntervals()
        self.f.add(1, 5, "a")
        self.f.add(4, 9, "b")
        self.f.add(9, 9, "empty")

    def test_left_closed(self):
        self.assertEqual(self.f.point_hit(1), ["a"])

    def test_right_open(self):
        self.assertEqual(self.f.point_hit(5), ["b"])

    def test_inside_multiple(self):
        self.assertEqual(sorted(self.f.point_hit(4)), ["a", "b"])

    def test_outside(self):
        self.assertEqual(self.f.point_hit(0), [])
        self.assertEqual(self.f.point_hit(9), [])
        self.assertEqual(self.f.point_hit(100), [])


class TestMergeAll(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(FlatIntervals().merge_all(), [])

    def test_single(self):
        f = FlatIntervals()
        f.add(2, 6, "a")
        self.assertEqual(f.merge_all(), [(2, 6)])

    def test_overlapping_merged(self):
        f = FlatIntervals()
        f.add(1, 5, "a")
        f.add(3, 7, "b")
        f.add(6, 9, "c")
        self.assertEqual(f.merge_all(), [(1, 9)])

    def test_disjoint_kept(self):
        f = FlatIntervals()
        f.add(1, 2, "a")
        f.add(5, 6, "b")
        self.assertEqual(f.merge_all(), [(1, 2), (5, 6)])

    def test_touching_merged(self):
        f = FlatIntervals()
        f.add(1, 2, "a")
        f.add(2, 3, "b")
        self.assertEqual(f.merge_all(), [(1, 3)])

    def test_contained(self):
        f = FlatIntervals()
        f.add(1, 10, "outer")
        f.add(3, 4, "inner")
        self.assertEqual(f.merge_all(), [(1, 10)])

    def test_degenerate_kept_apart(self):
        f = FlatIntervals()
        f.add(1, 3, "a")
        f.add(5, 5, "empty")
        f.add(7, 9, "b")
        self.assertEqual(f.merge_all(), [(1, 3), (5, 5), (7, 9)])


if __name__ == "__main__":
    unittest.main()
