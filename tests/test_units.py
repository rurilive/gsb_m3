"""切段行为的锁定测试。"""

import random
import unittest

from bytetok.units import (
    is_separator,
    join_segments,
    segment_frequencies,
    split_segments,
)


class TestSeparators(unittest.TestCase):
    def test_ascii_whitespace_and_punctuation_are_separators(self):
        for value in b" \t\n\r\x0b\x0c,.;:!?-_/()[]":
            self.assertTrue(is_separator(value))

    def test_word_bytes_are_not_separators(self):
        for value in b"aZ09\x00\x7f":
            self.assertFalse(is_separator(value))

    def test_high_bytes_are_word_bytes(self):
        # 0x80 以上一律算词字节，多字节 UTF-8 与 CJK 标点都靠这条保证不被切开
        for value in range(0x80, 0x100):
            self.assertFalse(is_separator(value))

    def test_rejects_non_int(self):
        with self.assertRaises(TypeError):
            is_separator(b" ")


class TestSplitSegments(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(split_segments(b""), [])

    def test_pure_word(self):
        self.assertEqual(split_segments(b"hello"), [b"hello"])

    def test_separator_run_is_one_segment(self):
        self.assertEqual(split_segments(b"a - b"), [b"a", b" - ", b"b"])
        self.assertEqual(split_segments(b",,"), [b",,"])

    def test_leading_and_trailing_separators(self):
        self.assertEqual(split_segments(b" hi "), [b" ", b"hi", b" "])

    def test_alternating(self):
        self.assertEqual(
            split_segments(b"x!y?"),
            [b"x", b"!", b"y", b"?"],
        )

    def test_multibyte_text_stays_in_word_segment(self):
        text = "你好,world".encode("utf-8")
        self.assertEqual(
            split_segments(text),
            ["你好".encode("utf-8"), b",", b"world"],
        )

    def test_cjk_punctuation_counts_as_word_byte(self):
        # 中文逗号是 0xEF 0xBC 0x8C，属于词字节，整段不被切开
        text = "你好，世界".encode("utf-8")
        self.assertEqual(split_segments(text), [text])

    def test_segments_cover_input_exactly(self):
        rng = random.Random(20260921)
        for _ in range(200):
            length = rng.randrange(0, 64)
            data = bytes(rng.randrange(0, 256) for _ in range(length))
            segments = split_segments(data)
            self.assertEqual(join_segments(segments), data)
            self.assertTrue(all(segments))

    def test_rejects_str(self):
        with self.assertRaises(TypeError):
            split_segments("abc")

    def test_frequencies_sorted_by_count_then_bytes(self):
        result = segment_frequencies(b"b b a")
        self.assertEqual(result, [(b" ", 2), (b"b", 2), (b"a", 1)])


if __name__ == "__main__":
    unittest.main()
