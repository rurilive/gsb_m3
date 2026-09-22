"""geocode 编解码与邻格的行为测试。"""

import unittest

from geogrid.errors import InvalidCoordinate
from geogrid.geocode import decode, encode, neighbors


class EncodeDecodeTest(unittest.TestCase):
    def test_known_geohash_vector(self):
        self.assertEqual(encode(57.64911, 10.40744, 11), "u4pruydqqvj")

    def test_decode_contains_the_encoded_point(self):
        spots = ((31.2304, 121.4737), (0.0, 0.0), (-33.8688, 151.2093), (89.9, -179.9))
        for lat, lon in spots:
            for precision in (1, 4, 7, 12):
                cell = decode(encode(lat, lon, precision))
                self.assertTrue(cell.contains(lat, lon), (lat, lon, precision, cell))

    def test_higher_precision_shrinks_the_cell(self):
        wide = decode(encode(31.2304, 121.4737, 3))
        tight = decode(encode(31.2304, 121.4737, 8))
        self.assertLess(tight.lat_max - tight.lat_min, wide.lat_max - wide.lat_min)
        self.assertLess(tight.lon_max - tight.lon_min, wide.lon_max - wide.lon_min)

    def test_truncation_keeps_the_original_cell_inside(self):
        for lat, lon in ((31.2304, 121.4737), (-12.7, 179.99), (80.0, -5.0)):
            full = encode(lat, lon, 9)
            inner = decode(full)
            for cut in (1, 2, 5, 8):
                outer = decode(full[:cut])
                self.assertTrue(outer.contains(inner.lat_min, inner.lon_min))
                self.assertTrue(outer.contains(inner.lat_max, inner.lon_max))

    def test_decode_center_reencodes_to_the_same_code(self):
        code = encode(31.2304, 121.4737, 7)
        lat, lon = decode(code).center
        self.assertEqual(encode(lat, lon, 7), code)

    def test_lon_is_normalized_before_encoding(self):
        self.assertEqual(encode(10.0, 180.0, 6), encode(10.0, -180.0, 6))
        self.assertEqual(encode(10.0, 190.0, 6), encode(10.0, -170.0, 6))

    def test_bad_input_rejected(self):
        with self.assertRaises(InvalidCoordinate):
            encode(91.0, 0.0)
        with self.assertRaises(InvalidCoordinate):
            encode(0.0, float("nan"))
        for bad in (0, -1, 1.5, "3", True):
            with self.assertRaises(ValueError):
                encode(0.0, 0.0, bad)
        for bad in ("", "a!c", "hello world", None, 123):
            with self.assertRaises(InvalidCoordinate):
                decode(bad)


class NeighborsTest(unittest.TestCase):
    def test_eight_neighbours_one_step_away(self):
        code = encode(31.2304, 121.4737, 5)
        cell = decode(code)
        lat_step = cell.lat_max - cell.lat_min
        lon_step = cell.lon_max - cell.lon_min
        clat, clon = cell.center
        offsets = set()
        ring = neighbors(code)
        self.assertEqual(len(ring), 8)
        self.assertNotIn(code, ring)
        for other in ring:
            self.assertEqual(len(other), len(code))
            olat, olon = decode(other).center
            offsets.add((round((olat - clat) / lat_step), round((olon - clon) / lon_step)))
        want = {(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)} - {(0, 0)}
        self.assertEqual(offsets, want)

    def test_antimeridian_neighbours_wrap(self):
        code = encode(0.0, 179.9999, 4)
        cell = decode(code)
        self.assertAlmostEqual(cell.lon_max, 180.0)
        wrapped = [c for c in neighbors(code) if decode(c).lon_min < -179.0]
        # 东北、正东、东南三格都绕到 -180 度起
        self.assertEqual(len(wrapped), 3)

    def test_pole_row_drops_the_polar_neighbours(self):
        code = encode(89.9999, 0.0, 4)
        cell = decode(code)
        self.assertAlmostEqual(cell.lat_max, 90.0)
        self.assertEqual(len(neighbors(code)), 5)

    def test_bad_code_rejected(self):
        with self.assertRaises(InvalidCoordinate):
            neighbors("!!")


if __name__ == "__main__":
    unittest.main()
