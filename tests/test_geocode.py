"""geohash 编解码与邻格。"""

import random
import unittest

from geogrid.errors import InvalidCoordinate
from geogrid.geocode import decode, encode, neighbors


class EncodeTest(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(encode(57.64911, 10.40744, 11), "u4pruydqqvj")

    def test_precision_controls_length(self):
        for precision in (1, 5, 12):
            self.assertEqual(len(encode(31.2304, 121.4737, precision)), precision)

    def test_lon_is_normalized(self):
        self.assertEqual(encode(10.0, 190.0, 8), encode(10.0, -170.0, 8))
        self.assertEqual(encode(10.0, 180.0, 8), encode(10.0, -180.0, 8))

    def test_bad_input_rejected(self):
        for lat, lon in ((91.0, 0.0), (0.0, float("nan")), ("0", 0.0)):
            with self.assertRaises(InvalidCoordinate):
                encode(lat, lon, 6)
        for bad in (0, -1, 100, 2.5, "6", True):
            with self.assertRaises(ValueError):
                encode(0.0, 0.0, bad)


class DecodeTest(unittest.TestCase):
    def test_decode_contains_the_original_point(self):
        rng = random.Random(20260922)
        for _ in range(500):
            lat = rng.uniform(-90.0, 90.0)
            lon = rng.uniform(-180.0, 180.0)
            precision = rng.randint(1, 12)
            lat_min, lat_max, lon_min, lon_max = decode(encode(lat, lon, precision))
            self.assertLessEqual(lat_min, lat)
            self.assertLessEqual(lat, lat_max)
            self.assertLessEqual(lon_min, lon)
            self.assertLessEqual(lon, lon_max)

    def test_truncated_code_decodes_to_a_covering_range(self):
        rng = random.Random(7)
        for _ in range(200):
            lat = rng.uniform(-90.0, 90.0)
            lon = rng.uniform(-180.0, 180.0)
            full = encode(lat, lon, 12)
            inner = decode(full)
            for precision in range(1, 12):
                prefix = full[:precision]
                self.assertEqual(prefix, encode(lat, lon, precision))
                lat_min, lat_max, lon_min, lon_max = decode(prefix)
                self.assertLessEqual(lat_min, inner[0])
                self.assertLessEqual(inner[1], lat_max)
                self.assertLessEqual(lon_min, inner[2])
                self.assertLessEqual(inner[3], lon_max)

    def test_bad_code_rejected(self):
        for bad in ("", "a", "hello!", "wtw3sj*", None, 123):
            with self.assertRaises(InvalidCoordinate):
                decode(bad)


class NeighborsTest(unittest.TestCase):
    def test_eight_neighbors_surround_the_cell(self):
        code = encode(31.2304, 121.4737, 6)
        lat_min, lat_max, lon_min, lon_max = decode(code)
        lat_step = lat_max - lat_min
        lon_step = lon_max - lon_min
        lat_center = (lat_min + lat_max) / 2.0
        lon_center = (lon_min + lon_max) / 2.0
        around = neighbors(code)
        self.assertEqual(len(around), 8)
        self.assertNotIn(code, around)
        offsets = set()
        for other in around:
            self.assertEqual(len(other), len(code))
            o_lat_min, o_lat_max, o_lon_min, o_lon_max = decode(other)
            dlat = round(((o_lat_min + o_lat_max) / 2.0 - lat_center) / lat_step)
            dlon = round(((o_lon_min + o_lon_max) / 2.0 - lon_center) / lon_step)
            offsets.add((dlat, dlon))
        expected = {(da, do) for da in (1, 0, -1) for do in (1, 0, -1)} - {(0, 0)}
        self.assertEqual(offsets, expected)

    def test_neighbors_connect_across_the_antimeridian(self):
        east_edge = encode(0.0, 179.9999, 5)
        wrapped = [decode(code) for code in neighbors(east_edge)]
        self.assertTrue(any(lon_min < -179.0 for _, _, lon_min, _ in wrapped))
        west_edge = encode(0.0, -179.9999, 5)
        wrapped = [decode(code) for code in neighbors(west_edge)]
        self.assertTrue(any(lon_max > 179.0 for _, _, _, lon_max in wrapped))

    def test_pole_side_has_no_beyond_pole_neighbors(self):
        near_pole = encode(89.9999, 0.0, 5)
        around = neighbors(near_pole)
        self.assertEqual(len(around), 5)
        for code in around:
            _, lat_max, _, _ = decode(code)
            self.assertLessEqual(lat_max, 90.0)


if __name__ == "__main__":
    unittest.main()
