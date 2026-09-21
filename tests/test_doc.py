"""TextDoc 的行为基线。rope 实现要跟这套口径逐字符对上。"""

import unittest

from ropepad import CHUNK, RangeError, TextDoc


class TextDocTest(unittest.TestCase):
    def test_insert_and_delete(self):
        empty = TextDoc()
        self.assertEqual((len(empty), empty.text(), empty.stats()["length"]), (0, "", 0))
        self.assertEqual(list(empty.iter_range(0, 99)), [])
        d = TextDoc("hello world")
        d.insert(5, ",")
        d.insert(12, "!")
        self.assertEqual(d.text(), "hello, world!")
        d.delete(5, 1)
        d.delete(0, 6)
        d.insert(0, "the ")
        self.assertEqual(d.text(), "the world!")

    def test_bounds(self):
        d = TextDoc("abc")
        for call in (lambda: d.insert(4, "x"), lambda: d.insert(-1, "x"),
                     lambda: d.delete(2, 2), lambda: d.delete(0, -1)):
            with self.assertRaises(RangeError):
                call()
        with self.assertRaises(TypeError):
            d.insert(1, b"bytes")
        d.delete(3, 0)
        self.assertEqual(d.text(), "abc")

    def test_noop_edits_do_nothing(self):
        d = TextDoc("abcdef")
        d.insert(3, "")
        d.delete(3, 0)
        self.assertEqual((d.text(), d.stats()["copied"]), ("abcdef", 0))

    def test_slice_is_a_copy(self):
        d = TextDoc("hello world")
        head = d.slice(0, 5)
        head.insert(5, "!")
        d.insert(0, ">")
        self.assertEqual((head.text(), d.text()), ("hello!", ">hello world"))
        self.assertEqual(d.slice(5, 5).text(), "")
        for start, end in ((-1, 2), (0, 99), (3, 2), (0, -1)):
            with self.assertRaises(RangeError):
                d.slice(start, end)

    def test_concat(self):
        a, b = TextDoc("foo"), TextDoc("bar")
        c = a.concat(b)
        c.insert(3, "-")
        self.assertEqual(c.text(), "foo-bar")
        self.assertEqual((a.text(), b.text()), ("foo", "bar"))

    def test_iter_range_clamps_tail(self):
        d = TextDoc("abcdef")
        self.assertEqual(list(d.iter_range(2, 99)), ["cdef"])
        self.assertEqual(list(d.iter_range(6, 99)), [])
        for start, end in ((-1, 3), (7, 7), (4, 3)):
            with self.assertRaises(RangeError):   # 当场就炸，不等第一次 next
                d.iter_range(start, end)

    def test_iter_range_matches_slice(self):
        d = TextDoc("x" * (CHUNK * 2 + 7))
        self.assertEqual("".join(d.iter_range(3, 2 * CHUNK + 5)),
                         d.slice(3, 2 * CHUNK + 5).text())
        for piece in d.iter_range(0, len(d)):
            self.assertLessEqual(len(piece), CHUNK)

    def test_wide_characters_are_single_positions(self):
        d = TextDoc("中文🙂abc")
        self.assertEqual(len(d), 6)
        self.assertEqual(d.slice(2, 3).text(), "🙂")
        d.insert(2, "字")
        d.delete(3, 1)
        self.assertEqual(d.text(), "中文字abc")

    def test_copied_grows_with_body(self):
        d = TextDoc("x" * 400)
        d.insert(200, "hello")
        self.assertGreater(d.stats()["copied"], 400)


if __name__ == "__main__":
    unittest.main()
