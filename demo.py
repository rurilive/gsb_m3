"""objlife 现状演示。

第一段：建一小片页面模型，数引用、放引用，看销毁回调怎么触发。
第二段：两个互相引用的节点，谁手里都不先归零。
第三段：从 roots 出发看可达子图，以及留给环回收与弱引用的位子。
"""

from objlife import ObjectStore, layers, reachable


def build_page(store):
    """页面的块结构：page 持有 header 和 body，两个块共用一份 style。"""
    page = store.create("page", {"name": "home"})
    header = store.create("block", {"role": "header"})
    body = store.create("block", {"role": "body"})
    style = store.create("style", {"sheet": "base.css"})

    store.link(page, header)
    store.link(page, body)
    store.link(header, style)
    store.link(body, style)

    store.release(style)   # 交给两个块撑着
    store.release(header)  # 交给 page 撑着
    store.release(body)
    return page


def main():
    died = []
    store = ObjectStore(on_destroy=lambda s, oid, kind, payload: died.append((oid, kind)))

    print("=== 建图 ===")
    page = build_page(store)
    for oid in store.ids():
        print("  oid=%-3d kind=%-6s count=%d out=%s" % (
            oid, store.kind(oid), store.refcount(oid), store.out_links(oid)))
    print("  stats:", store.stats())

    print("=== 前后指针：互相引用 ===")
    prev = store.create("cursor", {"tag": "prev"})
    nxt = store.create("cursor", {"tag": "next"})
    store.link(prev, nxt)
    store.link(nxt, prev)
    store.release(prev)
    store.release(nxt)
    print("  两个 cursor 谁也没到零，都还在：", store.ids())
    print("  stats:", store.stats())

    print("=== 从 roots 看可达子图 ===")
    roots = store.roots()
    for depth, level in enumerate(layers(store, roots)):
        print("  第 %d 层: %s" % (depth, level))
    print("  可达 %d 个，活对象 %d 个" % (
        len(reachable(store, roots)), store.stats()["alive"]))

    print("=== 放掉页面 ===")
    store.release(page)
    print("  销毁回调收到:", died)
    print("  还剩:", store.ids(), store.stats())

    # TODO(环回收与弱引用): collect() 与弱引用落地后，在这里补两段：
    # 两个 cursor 这类环能被扫描收掉，弱引用挂着的对象死后 get() 拿不到东西。


if __name__ == "__main__":
    main()
