"""genheap 现状演示。

第一段：建一小片对象图，看根、槽位与存活集合。
第二段：一轮全堆回收，看钩子按什么顺序回调、账目怎么涨。
第三段：环与自引用都收得掉。
第四段：钩子里还能继续分配，本轮新建的对象不会被顺手扫掉。
"""

from genheap import ObjectHeap


def build_page(heap):
    """页面的块结构：page 挂根，两个块共用一份样式对象。"""
    page = heap.alloc("page", {"name": "home"})
    header = heap.alloc("block", {"role": "header"})
    body = heap.alloc("block", {"role": "body"})
    style = heap.alloc("style", {"sheet": "base.css"})

    heap.add_root(page)
    heap.store(page, "header", header)
    heap.store(page, "body", body)
    heap.store(header, "style", style)
    heap.store(body, "style", style)
    return page, header, body, style


def dump(heap):
    for oid in heap.ids():
        pairs = [(slot, heap.load(oid, slot)) for slot in heap.slots(oid)]
        edges = ",".join("%s->%d" % (slot, dst) for slot, dst in pairs)
        print("  oid=%-2d kind=%-5s refs=[%s]" % (oid, heap.kind(oid), edges))


def main():
    print("=== 建图 ===")
    seen = []

    def on_free(heap, oid, kind, payload):
        seen.append((oid, kind))
        print("  收掉 oid=%d kind=%s payload=%s" % (oid, kind, payload))

    heap = ObjectHeap(on_free=on_free)
    page, header, body, style = build_page(heap)
    dump(heap)
    print("  roots:", heap.roots())
    print("  stats:", heap.stats())

    print("=== 换掉页面里的 header，再收一轮 ===")
    fresh = heap.alloc("block", {"role": "header"})
    heap.store(page, "header", fresh)
    print("  换下来的 header 没人引用了，本轮:", heap.collect())
    print("  钩子按顺序收到:", seen)

    print("=== 环与自引用 ===")
    a = heap.alloc("cursor", {"tag": "a"})
    b = heap.alloc("cursor", {"tag": "b"})
    c = heap.alloc("cursor", {"tag": "c"})
    heap.store(a, "next", b)
    heap.store(b, "next", c)
    heap.store(c, "next", a)
    heap.store(c, "self", c)
    report = heap.collect()
    print("  三个 cursor 成环且都不可达，收掉:", report["swept"])
    print("  stats:", heap.stats())

    print("=== 钩子里继续分配 ===")
    born = []

    def on_free_reentrant(heap, oid, kind, payload):
        made = heap.alloc("reborn", {"from": oid})
        born.append(made)
        print("  oid=%d 收掉时顺手建了 oid=%d" % (oid, made))

    other = ObjectHeap(on_free=on_free_reentrant)
    other.alloc("trash")
    report = other.collect()
    print("  本轮:", report, "新建的还在:", born,
          "alive:", other.stats()["alive"])

    # TODO(分代回收): minor_collect / major_collect / generation 落地后，
    # 在这里补两段：老年代堆大了以后，年轻代回收只扫年轻代那一小片；
    # 晋升阈值生效后老对象不再跟着年轻代一起被扫。


if __name__ == "__main__":
    main()
