"""Rope 的结构与性能验收：叶子复用、树高、拷贝量、迭代内存、随机对拍。

行为口径的基线在 test_rope.py，这里只量结构性质：编辑只重造受影响的路径，
没碰到的叶子 id 必须照旧；切片与拼接出的新 rope 与原体互相独立；顺序灌
十万个小块树深不超 64；单次编辑的拷贝量不随正文长度涨；大区间迭代不物化
整段。随机编辑序列下与 TextDoc 逐字符对拍，多字节字符也算一个位置。
"""

import random
import tracemalloc
import unittest

from ropepad import MAX_LEAF, RangeError, Rope, TextBuffer, TextDoc

ALPHABET = "ab中文🙂🐍 \n"


def big_rope(leaves=64):
    """造一条多叶子的大 rope，返回 (rope, 正文)。"""
    text = "".join(random.choice(ALPHABET) for _ in range(leaves * MAX_LEAF))
    return Rope.from_text(text), text


class LeafReuseTest(unittest.TestCase):
    def setUp(self):
        random.seed(183)

    def test_insert_keeps_untouched_leaves(self):
        rope, _ = big_rope()
        before = rope.leaf_ids()
        rope.insert(len(rope) // 2, "插入一段")
        after = rope.leaf_ids()
        kept = [i for i in after if i in set(before)]
        # 只有被切到的那个叶子该换，其余 id 照旧
        self.assertGreaterEqual(len(kept), len(before) - 1)
        self.assertGreaterEqual(len(kept), 1)

    def test_delete_keeps_untouched_leaves(self):
        rope, _ = big_rope()
        before = rope.leaf_ids()
        rope.delete(len(rope) // 2, 10)         # 区间落在至多两个叶子里
        after = rope.leaf_ids()
        kept = [i for i in after if i in set(before)]
        self.assertGreaterEqual(len(kept), len(before) - 2)

    def test_slice_shares_inner_leaves(self):
        rope, _ = big_rope()
        before = set(rope.leaf_ids())
        piece = rope.slice(MAX_LEAF + 3, 5 * MAX_LEAF - 3)
        fresh = [i for i in piece.leaf_ids() if i not in before]
        # 只有两端的边界叶子可能是新切的，中间叶子整个共享
        self.assertLessEqual(len(fresh), 2)
        self.assertEqual(len(piece.leaf_ids()), 4)

    def test_concat_shares_everything(self):
        a, _ = big_rope(8)
        b, _ = big_rope(8)
        ids = set(a.leaf_ids()) | set(b.leaf_ids())
        c = a.concat(b)
        self.assertTrue(set(c.leaf_ids()) <= ids)
        self.assertEqual(len(c.leaf_ids()), len(ids))

    def test_edits_are_path_copies(self):
        rope, _ = big_rope()
        before = rope.leaf_ids()
        rope.insert(0, "头")
        rope.insert(len(rope), "尾")
        rope.delete(len(rope) // 2, 5)
        kept = [i for i in rope.leaf_ids() if i in set(before)]
        self.assertGreaterEqual(len(kept), len(before) - 4)


class IndependenceTest(unittest.TestCase):
    def setUp(self):
        random.seed(184)

    def test_slice_and_source_drift_apart(self):
        rope, text = big_rope(16)
        piece = rope.slice(100, 9000)
        snapshot = piece.text()
        piece.insert(0, "改副本")
        piece.delete(len(piece) - 10, 10)
        rope.delete(0, 5000)
        rope.insert(100, "改本体")
        self.assertEqual(piece.text(), ("改副本" + snapshot)[:-10])
        self.assertEqual(rope.text(), text[5000:5100] + "改本体" + text[5100:])

    def test_concat_sources_stay_put(self):
        a, ta = big_rope(8)
        b, tb = big_rope(8)
        c = a.concat(b)
        c.insert(len(a), "中缝")
        c.delete(0, 100)
        self.assertEqual((a.text(), b.text()), (ta, tb))
        self.assertEqual(c.text(), (ta + "中缝" + tb)[100:])


class DepthTest(unittest.TestCase):
    def test_sequential_small_inserts_stay_shallow(self):
        rope = Rope.from_text("")
        for i in range(100000):
            rope.insert(len(rope), "ab" if i % 2 else "c")
        self.assertEqual(rope.depth(), rope.stats()["depth"])
        self.assertLessEqual(rope.depth(), 64)
        self.assertEqual(len(rope), 150000)

    def test_random_small_inserts_stay_shallow(self):
        random.seed(185)
        rope = Rope.from_text("")
        for _ in range(20000):
            rope.insert(random.randrange(len(rope) + 1),
                        random.choice(("x", "yz")))
        self.assertLessEqual(rope.depth(), 64)

    def test_random_deletes_stay_shallow(self):
        random.seed(186)
        rope, _ = big_rope(64)
        for _ in range(20000):
            if len(rope) < 10:
                break
            start = random.randrange(len(rope) - 9)
            rope.delete(start, random.randrange(1, 10))
        self.assertLessEqual(rope.depth(), 64)


class CopyVolumeTest(unittest.TestCase):
    def setUp(self):
        random.seed(187)

    def test_copied_does_not_grow_with_body(self):
        samples = []
        for leaves in (4, 256):
            rope, _ = big_rope(leaves)
            before = rope.stats()["copied"]
            rope.insert(len(rope) // 2, "单次插入")
            rope.delete(len(rope) // 2, 7)
            samples.append(rope.stats()["copied"] - before)
        small, large = samples
        # 正文涨 64 倍，单次编辑的拷贝量不许跟着涨
        self.assertLessEqual(large, small + 4 * MAX_LEAF)
        self.assertLessEqual(large, 4 * MAX_LEAF)

    def test_textdoc_copied_grows_rope_does_not(self):
        text = "正文" * (256 * 1024)       # 1 MB 上下
        doc, rope = TextDoc(text), Rope.from_text(text)
        doc.insert(len(doc) // 2, "x")
        rope.insert(len(rope) // 2, "x")
        self.assertGreater(doc.stats()["copied"], len(text))
        self.assertLessEqual(rope.stats()["copied"], 2 * MAX_LEAF)

    def test_append_stream_edit_cost_stays_flat(self):
        rope = Rope.from_text("")
        for _ in range(20000):
            rope.insert(len(rope), "ab")
        # 正文已经 4 万字符，再编辑的单次拷贝量仍然是有界的常数
        before = rope.stats()["copied"]
        rope.insert(len(rope), "ab")
        rope.delete(0, 2)
        self.assertLessEqual(rope.stats()["copied"] - before, 2 * MAX_LEAF)


class IterMemoryTest(unittest.TestCase):
    def test_iter_range_does_not_materialize(self):
        random.seed(188)
        rope, text = big_rope(2048)      # 约 2 MB 正文
        tracemalloc.start()
        try:
            count = sum(len(piece) for piece in rope.iter_range(3, len(rope) - 3))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(count, len(text) - 6)
        # 内存峰值远小于整段正文：顺树吐块，不拼整段
        self.assertLess(peak, len(text) // 8)

    def test_chunks_are_leaf_sized(self):
        random.seed(189)
        rope, text = big_rope(40)
        pieces = list(rope.iter_range(11, len(rope) - 7))
        self.assertEqual("".join(pieces), text[11:len(text) - 7])
        for piece in pieces:
            self.assertLessEqual(len(piece), MAX_LEAF)


class LocateTest(unittest.TestCase):
    def test_every_position_lands_on_the_right_char(self):
        random.seed(190)
        rope, text = big_rope(20)
        for pos in range(len(text)):
            leaf, off = rope.locate(pos)
            self.assertEqual(leaf.text[off], text[pos])
        leaf, off = rope.locate(len(text))
        self.assertEqual(off, leaf.length)


class DifferentialTest(unittest.TestCase):
    def test_random_edits_match_textdoc(self):
        random.seed(191)
        doc, rope = TextDoc(""), Rope.from_text("")
        for _ in range(3000):
            op = random.random()
            n = len(doc)
            if op < 0.45:
                pos = random.randrange(n + 1)
                text = "".join(random.choice(ALPHABET)
                               for _ in range(random.randrange(1, 5)))
                doc.insert(pos, text)
                rope.insert(pos, text)
            elif op < 0.8 and n:
                start = random.randrange(n)
                count = random.randrange(1, min(n - start, 6) + 1)
                doc.delete(start, count)
                rope.delete(start, count)
            elif op < 0.9 and n:
                start = random.randrange(n + 1)
                end = random.randrange(start, n + 1)
                self.assertEqual(rope.slice(start, end).text(),
                                 doc.slice(start, end).text())
                self.assertEqual("".join(rope.iter_range(start, end + 3)),
                                 doc.text()[start:min(end + 3, n)])
            else:
                pos = random.randrange(n + 1) if n else 0
                leaf, off = rope.locate(pos)
                if pos == n:
                    self.assertEqual(off, 0 if leaf is None else leaf.length)
                else:
                    self.assertEqual(leaf.text[off], doc.text()[pos])
            self.assertEqual(rope.text(), doc.text())
            self.assertEqual(len(rope), len(doc))
        self.assertLessEqual(rope.depth(), 64)

    def test_random_edits_with_wide_chars_at_boundaries(self):
        random.seed(192)
        doc, rope = TextDoc("🙂中文"), Rope.from_text("🙂中文")
        for _ in range(1500):
            n = len(doc)
            if random.random() < 0.5:
                pos = random.randrange(n + 1)
                text = random.choice(("🙂", "中", "ab", "🐍🐍"))
                doc.insert(pos, text)
                rope.insert(pos, text)
            elif n:
                start = random.randrange(n)
                doc.delete(start, 1)
                rope.delete(start, 1)
            self.assertEqual(rope.text(), doc.text())
        for start in range(len(doc) + 1):
            for end in range(start, len(doc) + 1):
                self.assertEqual(rope.slice(start, end).text(),
                                 doc.slice(start, end).text())

    def test_buffer_with_rope_backend_matches_textdoc(self):
        random.seed(193)
        a = TextBuffer("初始正文🙂", make_doc=None)
        b = TextBuffer("初始正文🙂", make_doc=Rope.from_text)
        for _ in range(500):
            n = len(a)
            if random.random() < 0.5:
                pos = random.randrange(n + 1)
                text = random.choice(("插", "ab", "🙂"))
                a.insert(pos, text)
                b.insert(pos, text)
            elif n:
                start = random.randrange(n)
                count = random.randrange(1, min(n - start, 4) + 1)
                a.delete(start, count)
                b.delete(start, count)
            pos = random.randrange(len(a) + 1)
            a.set_mark("m", pos)
            b.set_mark("m", pos)
        self.assertEqual(b.text(), a.text())
        self.assertEqual((b.revision, b.mark("m")), (a.revision, a.mark("m")))
        self.assertEqual("".join(b.chunks(0, 10 ** 9)), a.text())


class EdgeSemanticsTest(unittest.TestCase):
    """空 rope、越界、迭代尾部截断：与 TextDoc 一字不差。"""

    def test_empty_rope_matches_textdoc(self):
        doc, rope = TextDoc(""), Rope.from_text("")
        self.assertEqual((len(rope), rope.text(), rope.depth()), (0, "", 0))
        self.assertEqual(list(rope.iter_range(0, 99)), list(doc.iter_range(0, 99)))
        self.assertEqual(rope.locate(0), (None, 0))
        rope.insert(0, "🙂")
        doc.insert(0, "🙂")
        rope.delete(0, 1)
        doc.delete(0, 1)
        self.assertEqual((len(rope), rope.text(), rope.depth()), (0, "", 0))
        self.assertEqual(rope.stats()["leaves"], 0)

    def test_out_of_range_matches_textdoc(self):
        doc, rope = TextDoc("abc中文"), Rope.from_text("abc中文")
        n = len(doc)
        calls = (
            lambda d: d.insert(n + 1, "x"),
            lambda d: d.insert(-1, "x"),
            lambda d: d.delete(n, 1),
            lambda d: d.delete(-1, 1),
            lambda d: d.delete(0, -1),
            lambda d: d.delete(n - 1, 2),
            lambda d: d.slice(-1, 2),
            lambda d: d.slice(0, n + 1),
            lambda d: d.slice(2, 1),
            lambda d: d.iter_range(-1, 2),
            lambda d: d.iter_range(n + 1, n + 5),
            lambda d: d.iter_range(3, 2),
        )
        for call in calls:
            with self.assertRaises(RangeError):
                call(rope)
            with self.assertRaises(RangeError):
                call(doc)
        with self.assertRaises(RangeError):
            rope.locate(-1)
        with self.assertRaises(RangeError):
            rope.locate(n + 1)
        self.assertEqual(rope.text(), doc.text())

    def test_tail_clamp_matches_textdoc(self):
        random.seed(194)
        rope, text = big_rope(6)
        doc = TextDoc(text)
        for start, end in ((0, 10 ** 9), (len(text), 10 ** 9),
                           (len(text) - 1, len(text) + 5), (3, 3)):
            self.assertEqual("".join(rope.iter_range(start, end)),
                             "".join(doc.iter_range(start, end)))


if __name__ == "__main__":
    unittest.main()
