"""ropepad 现状演示。

TextDoc 与 Rope 各做几次编辑，看 copied 和叶子 id 怎么变；
Buffer 换后端时行为不变；最后把正文拉到 2 MB 量一次编辑耗时。
"""

import time

from ropepad import Rope, TextBuffer, TextDoc

FILLER = "编辑器件的文本缓冲 the quick brown fox 0123456789 "


def fill(size):
    return (FILLER * (size // len(FILLER) + 1))[:size]


def show_doc_edits():
    print("=== TextDoc：整串重拼 ===")
    doc = TextDoc(fill(200))
    doc.insert(100, "光标的插入")
    doc.delete(0, 40)
    print("  长度 %d，copied %d（每次编辑都把整串抄一遍）" % (len(doc), doc.stats()["copied"]))


def show_rope_edits():
    print("=== Rope：平衡树，编辑只重造一条路径 ===")
    rope = Rope.from_text(fill(20000))
    before = rope.leaf_ids()
    rope.insert(10000, "光标的插入")
    after = rope.leaf_ids()
    kept = [i for i in after if i in set(before)]
    print("  长度 %d，leaves %d，depth %d" % (len(rope), rope.stats()["leaves"], rope.depth()))
    print("  编辑前叶子 %d 个，编辑后 %d 个，复用 %d 个（复用率 %.0f%%）" % (
        len(before), len(after), len(kept), 100.0 * len(kept) / max(len(after), 1)))
    leaf, off = rope.locate(5)
    print("  locate(5) 落在叶子偏移 %d，该叶子长 %d" % (off, leaf.length))


def show_buffer():
    print("=== TextBuffer：换后端不改行为 ===")
    for name, factory in (("TextDoc", None), ("Rope", Rope.from_text)):
        buf = TextBuffer("hello world", make_doc=factory)
        buf.set_mark("caret", 5)
        buf.insert(0, "say: ")
        buf.replace(5, 5, "there")
        print("  %-7s 正文 %r 标记 caret=%d 修订 %d 指标 %s" % (
            name, buf.text(), buf.mark("caret"), buf.revision, buf.stats()))


def show_timing():
    print("=== 正文一大，TextDoc 就卡；Rope 单次编辑耗时不变 ===")
    text = fill(2 * 1024 * 1024)
    for name, make in (("TextDoc", TextDoc), ("Rope", Rope.from_text)):
        doc = make(text)
        start = time.perf_counter()
        for i in range(5):
            doc.insert(i * 1000, "x")
        print("  %-7s 2 MB 正文上 5 次单字符插入：%.3f 秒，copied %d" % (
            name, time.perf_counter() - start, doc.stats()["copied"]))


def show_small_inserts():
    print("=== 顺序灌十万个一两个字符的小块 ===")
    rope = Rope.from_text("")
    start = time.perf_counter()
    for i in range(100000):
        rope.insert(len(rope), "ab" if i % 2 else "c")
    elapsed = time.perf_counter() - start
    stats = rope.stats()
    print("  长度 %d，leaves %d，depth %d（上限 64），总耗时 %.3f 秒" % (
        len(rope), stats["leaves"], stats["depth"], elapsed))
    before = rope.stats()["copied"]
    tick = time.perf_counter()
    rope.insert(len(rope) // 2, "x")
    print("  正文 %d 字符时单次插入：%.6f 秒，copied 增加 %d（不随正文长度涨）" % (
        len(rope), time.perf_counter() - tick, rope.stats()["copied"] - before))


def main():
    show_doc_edits()
    show_rope_edits()
    show_buffer()
    show_timing()
    show_small_inserts()


if __name__ == "__main__":
    main()
