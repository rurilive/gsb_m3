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
    print("=== Rope：现在只有一个叶子 ===")
    rope = Rope.from_text(fill(200))
    before = rope.leaf_ids()
    rope.insert(100, "光标的插入")
    after = rope.leaf_ids()
    kept = [i for i in after if i in set(before)]
    print("  长度 %d，leaves %d，depth %d" % (len(rope), rope.stats()["leaves"], rope.depth()))
    print("  编辑前叶子 %s" % before)
    print("  编辑后叶子 %s（一个都没留住，复用率 0）" % after)
    print("  复用的叶子: %s" % (kept or "无"))
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
    print("=== 正文一大，编辑就卡 ===")
    text = fill(2 * 1024 * 1024)
    for name, make in (("TextDoc", TextDoc), ("Rope", Rope.from_text)):
        doc = make(text)
        start = time.perf_counter()
        for i in range(5):
            doc.insert(i * 1000, "x")
        print("  %-7s 2 MB 正文上 5 次单字符插入：%.3f 秒，copied %d" % (
            name, time.perf_counter() - start, doc.stats()["copied"]))
    # TODO(rope 结构): 平衡树落地后在这里补上顺序插十万个小块的树高与单次编辑耗时。


def main():
    show_doc_edits()
    show_rope_edits()
    show_buffer()
    show_timing()


if __name__ == "__main__":
    main()
