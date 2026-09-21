"""TextBuffer 的行为基线：同一套用例分别跑 TextDoc 和 Rope 两种后端。"""

import unittest

from ropepad import RangeError, Rope, TextBuffer, TextDoc, TextError

BACKENDS = (("TextDoc", None), ("Rope", Rope.from_text))


class TextBufferTest(unittest.TestCase):
    def each(self, text=""):
        for name, factory in BACKENDS:
            with self.subTest(backend=name):
                yield TextBuffer(text, make_doc=factory)

    def test_edit_and_revision(self):
        for buf in self.each("hello world"):
            self.assertEqual(buf.revision, 0)
            buf.insert(5, ",")
            self.assertEqual(buf.text(), "hello, world")
            buf.delete(5, 1)
            buf.replace(6, 5, "there")
            self.assertEqual(buf.text(), "hello there")
            self.assertEqual((len(buf), buf.revision), (11, 3))

    def test_noop_replace_keeps_revision(self):
        for buf in self.each("abcdef"):
            buf.replace(3, 0, "")
            self.assertEqual((buf.text(), buf.revision), ("abcdef", 0))

    def test_edit_errors(self):
        for buf in self.each("abc"):
            for call in (lambda: buf.insert(4, "x"), lambda: buf.delete(2, 5),
                         lambda: buf.replace(1, 9, "x")):
                with self.assertRaises(RangeError):
                    call()
            self.assertEqual((buf.text(), buf.revision), ("abc", 0))

    def test_marks_follow_edits(self):
        for buf in self.each("hello world"):
            buf.set_mark("caret", 5)
            buf.set_mark("tail", 11)
            buf.insert(5, ",")          # 插入点不晚于标记，标记黏右下移
            self.assertEqual(buf.mark("caret"), 6)
            buf.insert(0, ">")
            self.assertEqual(buf.mark("tail"), 13)
            buf.delete(0, 7)            # 落进删除区间的标记拉到删除起点
            self.assertEqual((buf.mark("caret"), buf.mark("tail")), (0, 6))
            buf.replace(0, 5, "abc")    # 先删再插，语义和连做两次一模一样
            self.assertEqual(buf.text(), "abcd")
            self.assertEqual((buf.mark("caret"), buf.mark("tail")), (3, 4))
            with self.assertRaises(TextError):
                buf.mark("nobody")
            with self.assertRaises(RangeError):
                buf.set_mark("caret", 99)

    def test_chunks_match_text(self):
        for buf in self.each("x" * 3000 + "中文🙂" + "y" * 3000):
            whole = buf.text()
            self.assertEqual("".join(buf.chunks(100, 2500)), whole[100:2500])
            self.assertEqual("".join(buf.chunks(2998, 100000)), whole[2998:])
            with self.assertRaises(RangeError):
                buf.chunks(4000, 10)

    def test_stats_include_revision(self):
        for buf in self.each("abc"):
            for key in ("length", "copied", "revision"):
                self.assertIn(key, buf.stats())
            buf.insert(3, "de")
            self.assertEqual((buf.stats()["revision"], buf.stats()["length"]), (1, 5))


if __name__ == "__main__":
    unittest.main()
