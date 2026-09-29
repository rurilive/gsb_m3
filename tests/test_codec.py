"""LineCodec 现有行为的锁定测试：定宽行编码与解码。

只覆盖当前实现已经具备的能力。长度前缀、字段类型、校验和、变长编码、
流式解帧都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from framefmt import LineCodec


class TestEncode(unittest.TestCase):
    def test_pads_fields_to_width(self):
        codec = LineCodec([3, 4])
        self.assertEqual(codec.encode(["ab", "c"]), "ab c   ")

    def test_custom_fill(self):
        codec = LineCodec([3, 3], fill="0")
        self.assertEqual(codec.encode(["1", "22"]), "100220")

    def test_exact_width_no_padding(self):
        codec = LineCodec([2, 2])
        self.assertEqual(codec.encode(["ab", "cd"]), "abcd")

    def test_total_width(self):
        self.assertEqual(LineCodec([2, 3, 5]).total_width(), 10)

    def test_too_wide_field_rejected(self):
        codec = LineCodec([2])
        with self.assertRaises(ValueError):
            codec.encode(["abc"])

    def test_wrong_field_count_rejected(self):
        codec = LineCodec([2, 2])
        with self.assertRaises(ValueError):
            codec.encode(["ab"])


class TestDecode(unittest.TestCase):
    def test_splits_and_strips_fill(self):
        codec = LineCodec([3, 4])
        self.assertEqual(codec.decode("ab c   "), ["ab", "c"])

    def test_custom_fill(self):
        codec = LineCodec([3, 3], fill="0")
        self.assertEqual(codec.decode("100220"), ["1", "22"])

    def test_wrong_length_rejected(self):
        codec = LineCodec([2, 2])
        with self.assertRaises(ValueError):
            codec.decode("abc")

    def test_non_string_rejected(self):
        codec = LineCodec([2])
        with self.assertRaises(ValueError):
            codec.decode(123)


class TestRoundTrip(unittest.TestCase):
    def test_encode_then_decode(self):
        codec = LineCodec([4, 6, 3])
        values = ["id1", "name", "42"]
        self.assertEqual(codec.decode(codec.encode(values)), values)

    def test_round_trip_with_custom_fill(self):
        codec = LineCodec([3, 2], fill=".")
        values = ["a", "bb"]
        self.assertEqual(codec.decode(codec.encode(values)), values)


class TestConstruction(unittest.TestCase):
    def test_empty_widths_rejected(self):
        with self.assertRaises(ValueError):
            LineCodec([])

    def test_non_positive_width_rejected(self):
        with self.assertRaises(ValueError):
            LineCodec([0])
        with self.assertRaises(ValueError):
            LineCodec([2, -1])

    def test_bad_fill_rejected(self):
        with self.assertRaises(ValueError):
            LineCodec([2], fill="..")

    def test_repr(self):
        self.assertEqual(repr(LineCodec([2, 3])), "LineCodec(widths=[2, 3])")


if __name__ == "__main__":
    unittest.main()
