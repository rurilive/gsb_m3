"""box / circle 范围查询：与全量扫描对拍、跨 180 度线、高纬度、热点分裂与性能门槛。"""

import random
import time
import unittest

from geogrid.errors import InvalidCoordinate
from geogrid.geo import haversine_m
from geogrid.index import PointIndex


def brute_box(index, lat_min, lat_max, lon_min, lon_max):
    """全量扫描版的 box：经度从 lon_min 向东走到 lon_max。"""
    span = lon_max - lon_min
    if span < 360.0:
        span %= 360.0
    matched = []
    for pid, lat, lon in index.scan():
        if not lat_min <= lat <= lat_max:
            continue
        if span >= 360.0 or (lon - lon_min) % 360.0 <= span:
            matched.append(pid)
    return matched


def brute_circle(index, lat, lon, radius_m):
    """全量扫描版的 circle：逐点球面距离判定。"""
    return [
        pid
        for pid, plat, plon in index.scan()
        if haversine_m(plat, plon, lat, lon) <= radius_m
    ]


def random_points(rng, count, lat_lo=-85.0, lat_hi=85.0, lon_lo=-180.0, lon_hi=180.0,
                  prefix="p"):
    return [
        ("%s%d" % (prefix, i), rng.uniform(lat_lo, lat_hi), rng.uniform(lon_lo, lon_hi))
        for i in range(count)
    ]


class BoxTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(148)
        self.index = PointIndex()
        for pid, lat, lon in random_points(rng, 3000):
            self.index.add(pid, lat, lon)
        self.rng = rng

    def test_box_matches_brute_force(self):
        for _ in range(200):
            lat_min = self.rng.uniform(-90.0, 60.0)
            lat_max = lat_min + self.rng.uniform(0.0, 90.0 - lat_min)
            lon_min = self.rng.uniform(-180.0, 180.0)
            lon_max = lon_min + self.rng.uniform(0.0, 400.0)
            self.assertEqual(
                self.index.box(lat_min, lat_max, lon_min, lon_max),
                brute_box(self.index, lat_min, lat_max, lon_min, lon_max),
            )

    def test_box_across_the_antimeridian(self):
        index = PointIndex()
        index.add("east", 10.0, 179.9)
        index.add("west", 10.0, -179.9)
        index.add("on-line", 10.0, 180.0)
        index.add("far", 10.0, 0.0)
        got = index.box(0.0, 20.0, 170.0, -170.0)
        self.assertEqual(got, ["east", "west", "on-line"])
        self.assertEqual(index.box(0.0, 20.0, 170.0, 190.0), got)

    def test_box_full_longitude_span(self):
        index = PointIndex()
        index.add("a", 10.0, 0.0)
        index.add("b", 10.0, 179.0)
        index.add("c", 20.0, -50.0)
        self.assertEqual(index.box(0.0, 15.0, -180.0, 180.0), ["a", "b"])
        self.assertEqual(index.box(0.0, 15.0, 0.0, 360.0), ["a", "b"])

    def test_box_result_keeps_registration_order(self):
        index = PointIndex()
        for pid in ("z1", "y2", "x3"):
            index.add(pid, 1.0, 1.0)
        self.assertEqual(index.box(0.0, 2.0, 0.0, 2.0), ["z1", "y2", "x3"])

    def test_bad_box_rejected(self):
        with self.assertRaises(InvalidCoordinate):
            self.index.box(10.0, 5.0, 0.0, 1.0)
        with self.assertRaises(InvalidCoordinate):
            self.index.box(0.0, 91.0, 0.0, 1.0)
        with self.assertRaises(InvalidCoordinate):
            self.index.box(0.0, 1.0, 0.0, float("nan"))


class CircleTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(315)
        self.index = PointIndex()
        points = random_points(rng, 3000)
        points += random_points(rng, 500, lat_lo=60.0, lat_hi=88.0, prefix="h")
        points += random_points(rng, 500, lon_lo=170.0, lon_hi=180.0, prefix="e")
        points += random_points(rng, 500, lon_lo=-180.0, lon_hi=-170.0, prefix="w")
        for pid, lat, lon in points:
            self.index.add(pid, lat, lon)
        self.rng = rng

    def test_circle_matches_brute_force(self):
        for _ in range(150):
            lat = self.rng.uniform(-85.0, 85.0)
            lon = self.rng.uniform(-180.0, 180.0)
            radius = self.rng.uniform(100.0, 500000.0)
            self.assertEqual(
                self.index.circle(lat, lon, radius),
                brute_circle(self.index, lat, lon, radius),
            )

    def test_circle_at_high_latitude_matches_brute_force(self):
        for _ in range(80):
            lat = self.rng.uniform(60.0, 89.0) * self.rng.choice((1.0, -1.0))
            lon = self.rng.uniform(-180.0, 180.0)
            radius = self.rng.uniform(1000.0, 2000000.0)
            self.assertEqual(
                self.index.circle(lat, lon, radius),
                brute_circle(self.index, lat, lon, radius),
            )

    def test_circle_across_the_antimeridian(self):
        index = PointIndex()
        index.add("east", 0.0, 179.99)
        index.add("west", 0.0, -179.99)
        index.add("far", 0.0, 178.0)
        got = index.circle(0.0, 180.0, 3000.0)
        self.assertEqual(got, ["east", "west"])

    def test_circle_covering_the_pole(self):
        index = PointIndex()
        index.add("north-a", 89.0, 0.0)
        index.add("north-b", 89.0, 120.0)
        index.add("south", -89.0, 0.0)
        got = index.circle(88.0, 30.0, 300000.0)
        self.assertEqual(got, ["north-a", "north-b"])

    def test_circle_radius_in_meters(self):
        index = PointIndex()
        index.add("near", 31.2305, 121.4737)
        index.add("far", 31.3304, 121.4737)
        self.assertEqual(index.circle(31.2304, 121.4737, 3000.0), ["near"])
        self.assertEqual(index.circle(31.2304, 121.4737, 20000.0), ["near", "far"])

    def test_bad_circle_rejected(self):
        for bad in (-1.0, float("nan"), float("inf"), "3000"):
            with self.assertRaises(InvalidCoordinate):
                self.index.circle(0.0, 0.0, bad)
        with self.assertRaises(InvalidCoordinate):
            self.index.circle(91.0, 0.0, 100.0)


class HotspotTest(unittest.TestCase):
    def test_crowded_cell_splits_and_queries_stay_correct(self):
        rng = random.Random(99)
        index = PointIndex()
        for i in range(30000):
            index.add(
                "hot-%d" % i,
                31.2304 + rng.random() * 0.019,
                121.4737 + rng.random() * 0.019,
            )
        snap = index.stats()
        self.assertEqual(snap["cells"], 1)
        self.assertLess(snap["max_cell"], 1000)

        before = index.stats()["cells_visited"]
        got = index.circle(31.2404, 121.4837, 300.0)
        visited = index.stats()["cells_visited"] - before
        self.assertEqual(got, brute_circle(index, 31.2404, 121.4837, 300.0))
        self.assertLess(visited, 2000)

        got = index.box(31.2354, 31.2454, 121.4787, 121.4887)
        self.assertEqual(got, brute_box(index, 31.2354, 31.2454, 121.4787, 121.4887))

    def test_remove_empties_split_cells(self):
        rng = random.Random(5)
        index = PointIndex()
        ids = []
        for i in range(5000):
            pid = "s%d" % i
            ids.append(pid)
            index.add(pid, 31.23 + rng.random() * 0.04, 121.47 + rng.random() * 0.04)
        self.assertLess(index.stats()["max_cell"], 5000)
        for pid in ids:
            index.remove(pid)
        snap = index.stats()
        self.assertEqual(snap["cells"], 0)
        self.assertEqual(snap["max_cell"], 0)

    def test_identical_points_respect_depth_cap(self):
        index = PointIndex()
        for i in range(2000):
            index.add("same-%d" % i, 31.2304, 121.4737)
        self.assertEqual(len(index.circle(31.2304, 121.4737, 1.0)), 2000)
        self.assertEqual(index.at(31.2304, 121.4737), ["same-%d" % i for i in range(2000)])


class PerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(2026)
        cls.index = PointIndex()
        for pid, lat, lon in random_points(rng, 300000, 18.0, 53.0, 73.0, 135.0):
            cls.index.add(pid, lat, lon)

    def test_box_query_beats_full_scan_by_an_order_of_magnitude(self):
        args = (30.0, 30.5, 120.0, 120.5)
        expected = brute_box(self.index, *args)
        got = self.index.box(*args)
        self.assertEqual(got, expected)

        start = time.perf_counter()
        for _ in range(20):
            self.index.box(*args)
        indexed = (time.perf_counter() - start) / 20.0
        start = time.perf_counter()
        brute_box(self.index, *args)
        brute = time.perf_counter() - start
        self.assertLess(indexed * 10.0, brute)

    def test_circle_query_beats_full_scan_by_an_order_of_magnitude(self):
        args = (31.2304, 121.4737, 3000.0)
        expected = brute_circle(self.index, *args)
        got = self.index.circle(*args)
        self.assertEqual(got, expected)

        start = time.perf_counter()
        for _ in range(20):
            self.index.circle(*args)
        indexed = (time.perf_counter() - start) / 20.0
        start = time.perf_counter()
        brute_circle(self.index, *args)
        brute = time.perf_counter() - start
        self.assertLess(indexed * 10.0, brute)

    def test_hotspot_query_does_not_degrade(self):
        rng = random.Random(77)
        index = PointIndex()
        for i in range(50000):
            index.add(
                "hot-%d" % i,
                31.2304 + rng.random() * 0.04,
                121.4737 + rng.random() * 0.04,
            )
        args = (31.2504, 121.4937, 100.0)
        self.assertEqual(index.circle(*args), brute_circle(index, *args))

        before = index.stats()["cells_visited"]
        start = time.perf_counter()
        for _ in range(20):
            index.circle(*args)
        indexed = (time.perf_counter() - start) / 20.0
        visited = (index.stats()["cells_visited"] - before) / 20.0
        start = time.perf_counter()
        brute_circle(index, *args)
        brute = time.perf_counter() - start
        self.assertLess(indexed * 10.0, brute)
        self.assertLess(visited, 2000)


class StatsTest(unittest.TestCase):
    def test_cells_visited_accumulates_per_range_query(self):
        index = PointIndex()
        rng = random.Random(3)
        for pid, lat, lon in random_points(rng, 2000, 30.0, 32.0, 120.0, 122.0):
            index.add(pid, lat, lon)
        self.assertEqual(index.stats()["cells_visited"], 0)
        index.box(31.0, 31.1, 121.0, 121.1)
        small = index.stats()["cells_visited"]
        self.assertGreater(small, 0)
        index.box(30.0, 32.0, 120.0, 122.0)
        total = index.stats()["cells_visited"]
        self.assertGreater(total, small)

    def test_lookups_and_hits_cover_range_queries(self):
        index = PointIndex()
        index.add("a", 1.0, 1.0)
        index.box(0.0, 2.0, 0.0, 2.0)
        index.circle(10.0, 10.0, 100.0)
        snap = index.stats()
        self.assertEqual(snap["lookups"], 2)
        self.assertEqual(snap["hits"], 1)


if __name__ == "__main__":
    unittest.main()
