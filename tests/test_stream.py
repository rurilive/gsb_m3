"""StreamDecoder：任意切分喂入，结果与一次性 decode 完全一致。"""

import unittest

from packwire import StreamDecoder, decode, encode
from packwire.errors import DecodeError
from packwire.framing import MAX_DEPTH

from vectors import VECTORS

MALFORMED = [
    "1800",               # 非最短首部
    "1b00000000ffffffff",
    "1f",                 # 保留附加信息
    "c0",                 # 未知类型码
    "ff",
    "da3f800000",         # 非最短浮点
    "d97e01",             # 非规范 NaN
    "a2616201616102",     # 字段表乱序
    "a2616101616102",     # 字段表重键（同上字节，键相同即重键）
    "a10102",             # 非文本键
    "61ff",               # 坏 UTF-8
    "830102",             # 截断
    "0000",               # 尾部残留
    "5b" + "ff" * 8,      # 夸张长度头
]


def one_shot_offset(data):
    try:
        decode(data)
    except DecodeError as exc:
        return exc.offset
    return None


def stream_offset(data, chunk_size):
    decoder = StreamDecoder()
    try:
        for i in range(0, len(data), chunk_size):
            decoder.feed(data[i:i + chunk_size])
        decoder.finish()
    except DecodeError as exc:
        return exc.offset
    return None


class StreamVectorTests(unittest.TestCase):
    def test_vectors_fed_byte_by_byte(self):
        for value, hex_text in VECTORS:
            data = bytes.fromhex(hex_text)
            with self.subTest(value=value):
                decoder = StreamDecoder()
                for byte in data:
                    decoder.feed(bytes([byte]))
                # NaN 与自身不相等，比再编码字节
                self.assertEqual(encode(decoder.finish()), data)

    def test_vectors_fed_in_varied_chunks(self):
        for value, hex_text in VECTORS:
            data = bytes.fromhex(hex_text)
            for size in [2, 3, 5, max(1, len(data) - 1), len(data) + 10]:
                with self.subTest(value=value, size=size):
                    decoder = StreamDecoder()
                    for i in range(0, len(data), size):
                        decoder.feed(data[i:i + size])
                    self.assertEqual(encode(decoder.finish()), data)

    def test_empty_chunks_are_noops(self):
        data = encode([1, "a", [2]])
        decoder = StreamDecoder()
        decoder.feed(b"")
        decoder.feed(data[:2])
        decoder.feed(b"")
        decoder.feed(data[2:])
        self.assertEqual(decoder.finish(), [1, "a", [2]])

    def test_feed_accepts_bytearray_and_memoryview(self):
        data = encode({"k": [1, 2]})
        decoder = StreamDecoder()
        decoder.feed(bytearray(data[:3]))
        decoder.feed(memoryview(data)[3:])
        self.assertEqual(decoder.finish(), {"k": [1, 2]})


class StreamErrorTests(unittest.TestCase):
    def test_malformed_offsets_match_one_shot_for_all_splittings(self):
        for hex_text in MALFORMED:
            data = bytes.fromhex(hex_text)
            expected = one_shot_offset(data)
            self.assertIsNotNone(expected, hex_text)
            for size in [1, 2, 3, 7, len(data)]:
                with self.subTest(hex=hex_text, size=size):
                    self.assertEqual(stream_offset(data, size), expected)

    def test_finish_on_empty_stream(self):
        with self.assertRaises(DecodeError) as ctx:
            StreamDecoder().finish()
        self.assertEqual(ctx.exception.offset, 0)

    def test_finish_on_truncated_stream(self):
        data = encode([1, "xy", [2, 3]])
        decoder = StreamDecoder()
        decoder.feed(data[:-1])
        with self.assertRaises(DecodeError) as ctx:
            decoder.finish()
        self.assertEqual(ctx.exception.offset, len(data) - 1)

    def test_trailing_bytes_reported_at_value_end(self):
        data = encode([1, "abc"])
        decoder = StreamDecoder()
        with self.assertRaises(DecodeError) as ctx:
            decoder.feed(data + b"\x00")
        self.assertEqual(ctx.exception.offset, len(data))

    def test_deep_nesting_rejected_without_recursion_error(self):
        data = b"\x81" * (MAX_DEPTH * 3)
        for size in [1, 7, 1000]:
            with self.subTest(size=size):
                self.assertEqual(stream_offset(data, size), MAX_DEPTH)

    def test_feed_after_finish_rejected(self):
        decoder = StreamDecoder()
        decoder.feed(encode(1))
        decoder.finish()
        with self.assertRaises(DecodeError):
            decoder.feed(b"\x00")

    def test_finish_is_idempotent(self):
        decoder = StreamDecoder()
        decoder.feed(encode("ok"))
        self.assertEqual(decoder.finish(), "ok")
        self.assertEqual(decoder.finish(), "ok")

    def test_non_bytes_feed_rejected(self):
        with self.assertRaises(TypeError):
            StreamDecoder().feed("not bytes")


if __name__ == "__main__":
    unittest.main()
