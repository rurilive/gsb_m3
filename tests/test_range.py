"""box/circle 范围查询：与暴力扫描逐点对拍，外加性能门槛。"""

import random
import time
import unittest

from geogrid.errors import InvalidCoordinate
from geogrid.geo import haversine_m, normalize_lon
from geogrid.index import PointIndex


def brute_box(index, lat_min, lat_max, lon_min, lon_max):
    """暴力矩形：全量 scan 逐点判定，作为 box 的对拍基准。"""
    if lon_max - lon_min >= 360.0:
        spans = [(-180.0, 180.0)]
    else:
        lo = normalize_lon(lon_min)
        hi = normalize_lon(lon_max)
        spans = [(lo, hi)] if lo <= hi else [(lo, 180.0), (-180.0, hi)]
    return [
        pid
        for pid, lat, lon in index.scan()
        if lat_min <= lat <= lat_max and any(lo <= lon <= hi for lo, hi in spans)
    ]


def brute_circle(index, lat, lon, radius_m):
    """暴力圆形：全量 scan 逐点算球面距离，作为 circle 的对拍基准。"""
    return [
        pid
        for pid, plat, plon in index.scan()
        if haversine_m(lat, lon, plat, plon) <= radius_m
    ]


def build_mixed_index(n=4000, seed=20260922):
    """全球散点 + 跨经线带 + 高纬带 + 上海热点商圈的混合索引。"""
    rng = random.Random(seed)
    index = PointIndex()
    for i in range(n):
        kind = i % 10
        if kind < 4:
            lat = rng.uniform(-80.0, 80.0)
            lon = rng.uniform(-180.0, 180.0)
        elif kind < 6:
            lat = rng.uniform(-1.0, 1.0)
            lon = rng.choice((179.9, -179.9, 180.0, -180.0)) + rng.uniform(-0.05, 0.05)
        elif kind < 8:
            lat = rng.choice((75.0, 85.0, 89.0, -75.0, -85.0)) + rng.uniform(-0.5, 0.5)
            lon = rng.uniform(-180.0, 180.0)
        else:
            lat = 31.2304 + rng.uniform(-0.01, 0.01)
            lon = 121.4737 + rng.uniform(-0.01, 0.01)
        index.add("p%d" % i, lat, lon)
    return index


class BoxQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = build_mixed_index()

    def test_random_boxes_match_brute_force(self):
        rng = random.Random(99)
        for _ in range(80):
            lat1, lat2 = rng.uniform(-90, 90), rng.uniform(-90, 90)
            lon1, lon2 = rng.uniform(-180, 180), rng.uniform(-180, 180)
            lat_min, lat_max = min(lat1, lat2), max(lat1, lat2)
            got = self.index.box(lat_min, lat_max, lon1, lon2)
            self.assertEqual(got, brute_box(self.index, lat_min, lat_max, lon1, lon2))

    def test_antimeridian_boxes_match_brute_force(self):
        cases = [
            (-1.0, 1.0, 170.0, -170.0),
            (-1.0, 1.0, -170.0, 170.0),
            (-0.5, 0.5, 179.95, -179.95),
            (-90.0, 90.0, -180.0, 180.0),
            (-90.0, 90.0, 0.0, 360.0),
        ]
        for lat_min, lat_max, lon_min, lon_max in cases:
            got = self.index.box(lat_min, lat_max, lon_min, lon_max)
            self.assertEqual(
                got, brute_box(self.index, lat_min, lat_max, lon_min, lon_max), cases)

    def test_high_latitude_and_pole_boxes(self):
        index = self.index
        index.add("north-pole", 90.0, 0.0)
        index.add("south-pole", -90.0, 40.0)
        try:
            got = index.box(89.0, 90.0, -10.0, 10.0)
            self.assertEqual(got, brute_box(index, 89.0, 90.0, -10.0, 10.0))
            self.assertIn("north-pole", got)
            got = index.box(-90.0, -89.0, 30.0, 50.0)
            self.assertEqual(got, brute_box(index, -90.0, -89.0, 30.0, 50.0))
            self.assertIn("south-pole", got)
        finally:
            index.remove("north-pole")
            index.remove("south-pole")

    def test_results_follow_registration_order(self):
        index = PointIndex()
        index.add("a", 0.0, 0.0)
        index.add("b", 0.0, 0.001)
        index.add("c", 0.0, 0.002)
        index.remove("a")
        index.add("a", 0.0, 0.0)
        self.assertEqual(index.box(-1.0, 1.0, -1.0, 1.0), ["b", "c", "a"])

    def test_bad_box_args_rejected(self):
        index = PointIndex()
        with self.assertRaises(InvalidCoordinate):
            index.box(10.0, -10.0, 0.0, 1.0)
        with self.assertRaises(InvalidCoordinate):
            index.box(0.0, 91.0, 0.0, 1.0)
        with self.assertRaises(InvalidCoordinate):
            index.box(0.0, 1.0, 0.0, float("nan"))


class CircleQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = build_mixed_index()

    def test_random_circles_match_brute_force(self):
        rng = random.Random(7)
        for _ in range(80):
            lat = rng.uniform(-88.0, 88.0)
            lon = rng.uniform(-180.0, 180.0)
            radius = rng.choice((100.0, 1000.0, 5000.0, 50000.0, 500000.0))
            radius *= rng.uniform(0.5, 1.5)
            got = self.index.circle(lat, lon, radius)
            self.assertEqual(got, brute_circle(self.index, lat, lon, radius))

    def test_antimeridian_circles_match_brute_force(self):
        for lon in (179.9, -179.9, 180.0):
            got = self.index.circle(0.0, lon, 30000.0)
            self.assertEqual(got, brute_circle(self.index, 0.0, lon, 30000.0))

    def test_high_latitude_circles_match_brute_force(self):
        cases = [
            (85.0, 0.0, 50000.0),
            (89.5, 0.0, 100000.0),
            (-89.5, 30.0, 80000.0),
            (90.0, 0.0, 200000.0),
        ]
        for lat, lon, radius in cases:
            got = self.index.circle(lat, lon, radius)
            self.assertEqual(got, brute_circle(self.index, lat, lon, radius), (lat, lon, radius))

    def test_zero_radius_picks_only_the_same_coordinate(self):
        index = PointIndex()
        index.add("a", 31.2304, 121.4737)
        index.add("b", 31.2304, 121.4737)
        index.add("c", 31.2305, 121.4737)
        self.assertEqual(index.circle(31.2304, 121.4737, 0.0), ["a", "b"])

    def test_bad_radius_rejected(self):
        index = PointIndex()
        for bad in (-1.0, float("nan"), float("inf"), "100", True):
            with self.assertRaises(InvalidCoordinate):
                index.circle(0.0, 0.0, bad)


class SplitBehaviourTest(unittest.TestCase):
    def test_hotspot_splits_and_stays_correct(self):
        index = PointIndex(max_cell_points=8, max_depth=12)
        rng = random.Random(3)
        for i in range(2000):
            index.add("h%d" % i,
                      31.2304 + rng.uniform(-0.001, 0.001),
                      121.4737 + rng.uniform(-0.001, 0.001))
        snap = index.stats()
        self.assertGreater(snap["cells"], 50)
        self.assertLess(snap["max_cell"], 2000)
        got = index.circle(31.2304, 121.4737, 100.0)
        self.assertEqual(got, brute_circle(index, 31.2304, 121.4737, 100.0))

    def test_depth_cap_bounds_the_split(self):
        index = PointIndex(max_cell_points=4, max_depth=3)
        rng = random.Random(5)
        for i in range(500):
            index.add("d%d" % i,
                      31.2304 + rng.uniform(-0.0005, 0.0005),
                      121.4737 + rng.uniform(-0.0005, 0.0005))
        self.assertLessEqual(index.stats()["cells"], 4 ** 3)
        got = index.box(31.22, 31.24, 121.46, 121.48)
        self.assertEqual(got, brute_box(index, 31.22, 31.24, 121.46, 121.48))

    def test_remove_after_split_releases_leaf_cells(self):
        index = PointIndex(max_cell_points=4, max_depth=6)
        rng = random.Random(8)
        for i in range(200):
            index.add("r%d" % i,
                      31.2304 + rng.uniform(-0.001, 0.001),
                      121.4737 + rng.uniform(-0.001, 0.001))
        for i in range(0, 200, 2):
            index.remove("r%d" % i)
        got = index.circle(31.2304, 121.4737, 500.0)
        self.assertEqual(got, brute_circle(index, 31.2304, 121.4737, 500.0))
        for i in range(1, 200, 2):
            index.remove("r%d" % i)
        self.assertEqual(index.stats()["cells"], 0)

    def test_bad_split_params_rejected(self):
        for bad in (0, -1, 1.5, "8", True):
            with self.assertRaises(ValueError):
                PointIndex(max_cell_points=bad)
        for bad in (-1, 1.5, "8", True):
            with self.assertRaises(ValueError):
                PointIndex(max_depth=bad)
        PointIndex(max_depth=0)


class CellsVisitedTest(unittest.TestCase):
    def test_cells_visited_accumulates_per_query(self):
        index = build_mixed_index()
        self.assertEqual(index.stats()["cells_visited"], 0)
        index.box(31.0, 31.5, 121.0, 122.0)
        small = index.stats()["cells_visited"]
        self.assertGreater(small, 0)
        index.box(-90.0, 90.0, -180.0, 180.0)
        total = index.stats()["cells_visited"]
        self.assertGreater(total, small)
        index.circle(31.2304, 121.4737, 3000.0)
        self.assertGreater(index.stats()["cells_visited"], total)


class PerformanceTest(unittest.TestCase):
    """几十万点下，范围查询要比全量 scan 暴力判定快一个数量级。"""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(11)
        cls.index = PointIndex()
        hotspot = 20000
        total = 200000
        for i in range(total):
            if i < hotspot:
                lat = 31.2304 + rng.uniform(-0.01, 0.01)
                lon = 121.4737 + rng.uniform(-0.01, 0.01)
            else:
                lat = rng.uniform(18.0, 42.0)
                lon = rng.uniform(105.0, 125.0)
            cls.index.add(i, lat, lon)

    def _assert_faster_than_brute(self, name, query, brute):
        want = brute()
        got = query()
        self.assertEqual(got, want, name)
        t_query = min(self._time(query) for _ in range(5))
        t_brute = min(self._time(brute) for _ in range(2))
        self.assertLess(
            t_query * 10, t_brute,
            "%s: 查询 %.4fs 暴力 %.4fs，未达 10 倍" % (name, t_query, t_brute))

    @staticmethod
    def _time(fn):
        start = time.perf_counter()
        fn()
        return time.perf_counter() - start

    def test_sparse_box_beats_full_scan(self):
        self._assert_faster_than_brute(
            "稀疏区矩形",
            lambda: self.index.box(25.0, 25.05, 110.0, 110.05),
            lambda: brute_box(self.index, 25.0, 25.05, 110.0, 110.05))

    def test_hotspot_circle_beats_full_scan(self):
        before = self.index.stats()["cells_visited"]
        self._assert_faster_than_brute(
            "热点商圈圆",
            lambda: self.index.circle(31.2304, 121.4737, 500.0),
            lambda: brute_circle(self.index, 31.2304, 121.4737, 500.0))
        visited = self.index.stats()["cells_visited"] - before
        self.assertLess(visited, 2000, "热点下翻格过多，疑似退化")


if __name__ == "__main__":
    unittest.main()
