"""Rope 的行为基线：口径与 TextDoc 逐条对齐。"""

import unittest

from ropepad import MAX_LEAF, RangeError, Rope, TextDoc


class RopeTest(unittest.TestCase):
    def test_empty(self):
        r = Rope.from_text("")
        self.assertEqual((len(r), r.text(), r.depth(), r.leaf_ids()), (0, "", 0, []))
        self.assertEqual(r.locate(0), (None, 0))
        self.assertEqual(list(r.iter_range(0, 0)), [])
        with self.assertRaises(RangeError):
            r.locate(1)

    def test_from_text_and_stats(self):
        r = Rope.from_text("hello")
        s = r.stats()
        self.assertEqual((len(r), r.text(), s["length"]), (5, "hello", 5))
        self.assertEqual((s["leaves"], s["depth"]), (len(r.leaf_ids()), r.depth()))

    def test_insert_and_delete(self):
        r = Rope.from_text("hello world")
        r.insert(5, ",")
        r.insert(12, "!")
        self.assertEqual(r.text(), "hello, world!")
        r.delete(5, 1)
        r.delete(0, 6)
        self.assertEqual(r.text(), "world!")
        r.delete(0, 6)
        self.assertEqual((len(r), r.text(), r.depth()), (0, "", 0))

    def test_bounds(self):
        r = Rope.from_text("abc")
        for call in (lambda: r.insert(4, "x"), lambda: r.insert(-1, "x"),
                     lambda: r.delete(2, 2), lambda: r.delete(0, -1),
                     lambda: r.locate(-1), lambda: r.locate(4)):
            with self.assertRaises(RangeError):
                call()
        with self.assertRaises(TypeError):
            r.insert(1, b"bytes")

    def test_noop_edits_keep_structure(self):
        r = Rope.from_text("abcdef")
        ids, copied = r.leaf_ids(), r.stats()["copied"]
        r.insert(3, "")
        r.delete(3, 0)
        self.assertEqual(r.leaf_ids(), ids)
        self.assertEqual(r.stats()["copied"], copied)
        self.assertEqual(r.text(), "abcdef")

    def test_insert_into_empty_and_locate(self):
        r = Rope.from_text("")
        r.insert(0, "ab")
        r.insert(2, "cd")
        self.assertEqual(r.text(), "abcd")
        for pos in range(4):
            leaf, off = r.locate(pos)
            self.assertEqual(leaf.text[off], "abcd"[pos])
        self.assertEqual(r.locate(4)[1], 4)

    def test_slice_is_independent(self):
        r = Rope.from_text("hello world")
        head = r.slice(0, 5)
        head.insert(5, "!")
        r.insert(0, ">")
        self.assertEqual((head.text(), r.text()), ("hello!", ">hello world"))
        self.assertEqual(r.slice(5, 5).text(), "")
        for start, end in ((-1, 2), (0, 99), (3, 2), (0, -1)):
            with self.assertRaises(RangeError):
                r.slice(start, end)

    def test_concat_is_independent(self):
        a, b = Rope.from_text("foo"), Rope.from_text("bar")
        c = a.concat(b)
        c.insert(3, "-")
        self.assertEqual(c.text(), "foo-bar")
        self.assertEqual((a.text(), b.text()), ("foo", "bar"))
        self.assertEqual(Rope.from_text("").concat(a).text(), "foo")

    def test_iter_range_clamps_tail(self):
        r = Rope.from_text("abcdef")
        self.assertEqual(list(r.iter_range(2, 99)), ["cdef"])
        self.assertEqual(list(r.iter_range(6, 99)), [])
        for start, end in ((-1, 3), (7, 7), (4, 3)):
            with self.assertRaises(RangeError):   # 当场就炸，不等第一次 next
                r.iter_range(start, end)

    def test_iter_range_matches_slice(self):
        r = Rope.from_text("y" * (MAX_LEAF * 2 + 11))
        self.assertEqual("".join(r.iter_range(7, 2 * MAX_LEAF + 5)),
                         r.slice(7, 2 * MAX_LEAF + 5).text())
        for piece in r.iter_range(0, len(r)):
            self.assertLessEqual(len(piece), MAX_LEAF)

    def test_leaf_ids_track_the_structure(self):
        r = Rope.from_text("abcdef")
        ids = r.leaf_ids()
        self.assertEqual(len(ids), r.stats()["leaves"])
        self.assertEqual(len(set(ids)), len(ids))     # 叶子互不相同
        self.assertEqual(list(r.iter_range(0, len(r))), ["abcdef"])
        # 基线把整段正文塞进一个叶子，一次编辑整条换血，复用率永远是零。
        # 验收按 id 统计复用率：只有编辑路径上的叶子该换。
        r.insert(3, "XY")
        self.assertEqual(len(r.leaf_ids()), r.stats()["leaves"])

    def test_matches_textdoc_on_edits(self):
        doc, rope = TextDoc("中文🙂abc"), Rope.from_text("中文🙂abc")
        for op, pos, arg in (("insert", 2, "字"), ("delete", 3, 1), ("insert", 0, "头"),
                             ("delete", 0, 2), ("insert", 4, "🙂🙂")):
            if op == "insert":
                doc.insert(pos, arg)
                rope.insert(pos, arg)
            else:
                doc.delete(pos, arg)
                rope.delete(pos, arg)
            self.assertEqual(rope.text(), doc.text())
        for start in range(len(doc) + 1):
            for end in range(start, len(doc) + 1):
                self.assertEqual(rope.slice(start, end).text(), doc.slice(start, end).text())


if __name__ == "__main__":
    unittest.main()
