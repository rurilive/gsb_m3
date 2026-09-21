"""规范形与畸形输入的防守测试。

非最短形、保留附加信息、未知类型码、非最短浮点、字段表乱序/重键/
非文本键、嵌套过深、夸张长度头，都必须报 DecodeError 并带对偏移；
编码侧超深与超界报 EncodeError，不许爆栈。
"""

import unittest

from packwire import decode, encode
from packwire.errors import DecodeError, EncodeError
from packwire.framing import MAX_DEPTH

from vectors import VECTORS


class NonShortestHeadTests(unittest.TestCase):
    def test_non_shortest_heads_rejected_at_head_offset(self):
        cases = [
            "1800",                  # 0 用了一字节参数
            "1817",                  # 23 用了一字节参数
            "190018",                # 24 用了两字节参数
            "1900ff",                # 255 用了两字节参数
            "1a0000ffff",            # 65535 用了四字节参数
            "1b00000000ffffffff",    # 2**32-1 用了八字节参数
            "3800",                  # -1 用了一字节参数
            "7801" + "61",           # 文本长度 1 用了长形首部
            "9801" + "00",           # 数组计数 1 用了长形首部
            "b801" + "6161" + "00",  # 字段表计数 1 用了长形首部
        ]
        for hex_text in cases:
            data = bytes.fromhex(hex_text)
            with self.subTest(hex=hex_text):
                with self.assertRaises(DecodeError) as ctx:
                    decode(data)
                self.assertEqual(ctx.exception.offset, 0)

    def test_reserved_additional_info_rejected(self):
        for tag in [0x1C, 0x1D, 0x1E, 0x1F, 0x5F, 0x7F, 0x9F, 0xBF]:
            with self.subTest(tag=tag):
                with self.assertRaises(DecodeError) as ctx:
                    decode(bytes([tag]))
                self.assertEqual(ctx.exception.offset, 0)

    def test_unknown_type_codes_rejected(self):
        for data in [b"\xc0", b"\xd8\x00", b"\xe0", b"\xff"]:
            with self.subTest(data=data):
                with self.assertRaises(DecodeError) as ctx:
                    decode(data)
                self.assertEqual(ctx.exception.offset, 0)


class NonCanonicalFloatTests(unittest.TestCase):
    def test_non_shortest_floats_rejected(self):
        cases = [
            "da3f800000",            # 1.0 用单精度（半精度即可）
            "db3ff0000000000000",    # 1.0 用双精度
            "da00000000",            # 0.0 用单精度
            "db7ff0000000000000",    # inf 用双精度
            "d97e01",                # 非规范 NaN 载荷
            "da7fc00000",            # 单精度 NaN
        ]
        for hex_text in cases:
            with self.subTest(hex=hex_text):
                with self.assertRaises(DecodeError) as ctx:
                    decode(bytes.fromhex(hex_text))
                self.assertEqual(ctx.exception.offset, 0)


class MapCanonicalTests(unittest.TestCase):
    def test_out_of_order_keys_rejected(self):
        # 键 b 在 a 前：第二个键起于偏移 4
        with self.assertRaises(DecodeError) as ctx:
            decode(bytes.fromhex("a2" + "6162" + "01" + "6161" + "02"))
        self.assertEqual(ctx.exception.offset, 4)

    def test_length_order_violation_rejected(self):
        # 键 aa（2 字节）在 b（1 字节）前：第二个键起于偏移 5
        with self.assertRaises(DecodeError) as ctx:
            decode(bytes.fromhex("a2" + "626161" + "01" + "6162" + "02"))
        self.assertEqual(ctx.exception.offset, 5)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(DecodeError) as ctx:
            decode(bytes.fromhex("a2" + "6161" + "01" + "6161" + "02"))
        self.assertEqual(ctx.exception.offset, 4)

    def test_non_text_key_rejected(self):
        with self.assertRaises(DecodeError) as ctx:
            decode(bytes.fromhex("a1" + "01" + "02"))
        self.assertEqual(ctx.exception.offset, 1)

    def test_non_text_key_on_encode_rejected(self):
        with self.assertRaises(EncodeError):
            encode({1: "x"})


class DepthLimitTests(unittest.TestCase):
    def test_max_depth_minus_one_levels_decode_fine(self):
        data = b"\x81" * (MAX_DEPTH - 1) + b"\x00"
        value = decode(data)
        for _ in range(MAX_DEPTH - 1):
            value = value[0]
        self.assertEqual(value, 0)

    def test_too_deep_nesting_rejected_without_recursion_error(self):
        data = b"\x81" * (MAX_DEPTH * 3)
        with self.assertRaises(DecodeError) as ctx:
            decode(data)
        self.assertEqual(ctx.exception.offset, MAX_DEPTH)

    def test_too_deep_maps_rejected(self):
        data = b"\xa1\x61\x61" * (MAX_DEPTH * 3)
        with self.assertRaises(DecodeError):
            decode(data)

    def test_too_deep_encode_rejected_without_recursion_error(self):
        value = 0
        for _ in range(MAX_DEPTH * 3):
            value = [value]
        with self.assertRaises(EncodeError):
            encode(value)


class ExaggeratedLengthTests(unittest.TestCase):
    def test_huge_length_headers_report_truncation_not_allocation(self):
        cases = [
            "5b" + "ff" * 8,  # 字节串长度 2**64-1
            "7b" + "ff" * 8,  # 文本长度 2**64-1
            "9b" + "ff" * 8,  # 数组计数 2**64-1
            "bb" + "ff" * 8,  # 字段表计数 2**64-1
        ]
        for hex_text in cases:
            data = bytes.fromhex(hex_text)
            with self.subTest(hex=hex_text):
                with self.assertRaises(DecodeError) as ctx:
                    decode(data)
                self.assertEqual(ctx.exception.offset, len(data))


class TruncationPrefixTests(unittest.TestCase):
    def test_every_vector_prefix_is_truncation_at_input_end(self):
        for value, hex_text in VECTORS:
            data = bytes.fromhex(hex_text)
            for cut in range(len(data)):
                with self.subTest(value=value, cut=cut):
                    with self.assertRaises(DecodeError) as ctx:
                        decode(data[:cut])
                    self.assertEqual(ctx.exception.offset, cut)


if __name__ == "__main__":
    unittest.main()
