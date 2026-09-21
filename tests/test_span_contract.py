"""事故复盘锁死用例：跨度取整方向与归档打包编码。"""

import struct
import unittest

from stampkit import span


class DurationFloorTests(unittest.TestCase):
    def test_negative_partial_unit_floors(self):
        # -1999ms 按秒必须是 -2s（向负无穷），不能截断成 -1s。
        self.assertEqual(span.duration_between(1_999, 0, "s"), -2)
        self.assertEqual(span.duration_between(0, -1_999, "s"), -2)

    def test_half_unit_directions(self):
        self.assertEqual(span.duration_between(0, 1_500, "s"), 1)
        self.assertEqual(span.duration_between(0, -1_500, "s"), -2)
        self.assertEqual(span.duration_between(-1_500, 0, "s"), 1)

    def test_exact_units(self):
        self.assertEqual(span.duration_between(0, -90_000, "s"), -90)
        self.assertEqual(span.duration_between(0, 3_600_000, "h"), 1)


class PackDurationContractTests(unittest.TestCase):
    def test_payload_is_millis_little_endian_signed(self):
        self.assertEqual(span.pack_duration(90_000), struct.pack("<q", 90_000))
        self.assertEqual(span.pack_duration(-1_500), struct.pack("<q", -1_500))

    def test_centuries_round_trip(self):
        # 几百年的毫秒跨度必须能进有符号 64 位且原样解回。
        year_ms = 365 * 86_400 * 1_000
        for years in (100, 500, 999):
            value = years * year_ms
            blob = span.pack_duration(value)
            self.assertEqual(len(blob), 8)
            self.assertEqual(span.unpack_duration(blob), value)
            self.assertEqual(span.unpack_duration(span.pack_duration(-value)), -value)

    def test_int64_limits_round_trip(self):
        self.assertEqual(span.unpack_duration(span.pack_duration(2**63 - 1)), 2**63 - 1)
        self.assertEqual(span.unpack_duration(span.pack_duration(-(2**63))), -(2**63))

    def test_out_of_range_raises(self):
        with self.assertRaises(struct.error):
            span.pack_duration(2**63)


if __name__ == "__main__":
    unittest.main()
