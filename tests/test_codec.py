"""encode/decode 既有行为的锁定测试。

这里只锁语义（往返一致、错误分类、偏移约定），不锁具体字节布局，
免得以后换线格式时误伤。
"""

import unittest

from packwire import decode, encode
from packwire.errors import DecodeError, EncodeError


class RoundTripTests(unittest.TestCase):
    def test_integer_round_trips(self):
        values = [0, 1, 7, 255, 256, 65535, 1 << 40, -1, -7, -256, -65536, -(1 << 40)]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(decode(encode(value)), value)

    def test_text_round_trips(self):
        texts = ["", "a", "hello", "多字节文本", "line\nbreak", "café"]
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(decode(encode(text)), text)

    def test_container_round_trips(self):
        values = [
            [],
            [[]],
            [[], []],
            [1, "a", [-2, ["deep", []]], "z"],
            [[1], [2, [3, [4, "end"]]]],
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(decode(encode(value)), value)

    def test_encode_returns_bytes(self):
        self.assertIsInstance(encode([1, "a"]), bytes)

    def test_bool_encodes_as_plain_integer(self):
        got = decode(encode(True))
        self.assertEqual(got, 1)
        self.assertNotIsInstance(got, bool)
        self.assertEqual(decode(encode(False)), 0)


class EncodeGuardTests(unittest.TestCase):
    def test_unsupported_values_rejected(self):
        for value in [object(), {1, 2}, ("tuple",), 3 + 4j]:
            with self.subTest(value=value):
                with self.assertRaises(EncodeError):
                    encode(value)

    def test_integer_beyond_64_bits_rejected(self):
        with self.assertRaises(EncodeError):
            encode(1 << 64)

    def test_lone_surrogate_text_rejected(self):
        with self.assertRaises(EncodeError):
            encode("\ud800")


class DecodeGuardTests(unittest.TestCase):
    def test_empty_input(self):
        with self.assertRaises(DecodeError) as ctx:
            decode(b"")
        self.assertEqual(ctx.exception.offset, 0)

    def test_truncated_input(self):
        for value in [5, "abc", [1, 2, 3], [1, "xy"]]:
            data = encode(value)
            with self.subTest(value=value):
                with self.assertRaises(DecodeError) as ctx:
                    decode(data[:-1])
                self.assertEqual(ctx.exception.offset, len(data) - 1)

    def test_trailing_bytes(self):
        data = encode([1, "abc"])
        with self.assertRaises(DecodeError) as ctx:
            decode(data + b"\x00")
        self.assertEqual(ctx.exception.offset, len(data))

    def test_garbage_input(self):
        with self.assertRaises(DecodeError):
            decode(b"\x02\xff\xff\xff\xff")

    def test_non_bytes_input_rejected(self):
        with self.assertRaises(TypeError):
            decode("not bytes")


if __name__ == "__main__":
    unittest.main()
