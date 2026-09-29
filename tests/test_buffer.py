"""基础字符串缓冲现有行为的锁定测试。

只覆盖当前实现已具备的能力：构造与 text 副本、按下标插入、按下标删除、
长度与字符串化，以及越界与类型校验。
"""

import unittest

from colitext.buffer import TextBuf, ColitextError


class TestTextBufBasics(unittest.TestCase):
    def test_starts_empty(self):
        buf = TextBuf()
        self.assertEqual(buf.text(), "")
        self.assertEqual(len(buf), 0)

    def test_construct_with_text(self):
        buf = TextBuf("hello")
        self.assertEqual(buf.text(), "hello")
        self.assertEqual(len(buf), 5)

    def test_insert_returns_self(self):
        buf = TextBuf("ac")
        self.assertIs(buf.insert(1, "b"), buf)
        self.assertEqual(buf.text(), "abc")

    def test_insert_at_start_and_end(self):
        buf = TextBuf("bc")
        buf.insert(0, "a")
        buf.insert(len(buf), "d")
        self.assertEqual(buf.text(), "abcd")

    def test_insert_empty_text_is_noop(self):
        buf = TextBuf("ab")
        buf.insert(1, "")
        self.assertEqual(buf.text(), "ab")

    def test_delete_returns_self(self):
        buf = TextBuf("abc")
        self.assertIs(buf.delete(1), buf)
        self.assertEqual(buf.text(), "ac")

    def test_delete_multiple_characters(self):
        buf = TextBuf("abcdef")
        buf.delete(1, 3)
        self.assertEqual(buf.text(), "aef")

    def test_delete_zero_is_noop(self):
        buf = TextBuf("ab")
        buf.delete(1, 0)
        self.assertEqual(buf.text(), "ab")

    def test_text_returns_independent_copy(self):
        buf = TextBuf("ab")
        snap = buf.text()
        buf.insert(2, "c")
        self.assertEqual(snap, "ab")
        self.assertEqual(buf.text(), "abc")

    def test_str_and_repr(self):
        buf = TextBuf("ab")
        self.assertEqual(str(buf), "ab")
        self.assertEqual(repr(buf), "TextBuf('ab')")


class TestTextBufValidation(unittest.TestCase):
    def test_construct_rejects_non_string(self):
        with self.assertRaises(ColitextError):
            TextBuf(1)

    def test_insert_rejects_non_string_text(self):
        buf = TextBuf()
        with self.assertRaises(ColitextError):
            buf.insert(0, 1)

    def test_insert_rejects_out_of_range_index(self):
        buf = TextBuf("ab")
        with self.assertRaises(ColitextError):
            buf.insert(3, "c")

    def test_insert_rejects_negative_index(self):
        buf = TextBuf("ab")
        with self.assertRaises(ColitextError):
            buf.insert(-1, "c")

    def test_delete_rejects_out_of_bounds_range(self):
        buf = TextBuf("ab")
        with self.assertRaises(ColitextError):
            buf.delete(1, 5)

    def test_delete_rejects_negative_count(self):
        buf = TextBuf("ab")
        with self.assertRaises(ColitextError):
            buf.delete(0, -1)


if __name__ == "__main__":
    unittest.main()
