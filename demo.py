"""bucketmap 用法演示：单线程读写、扩容过程、多线程并发、参考实现。

python3 demo.py 直接跑，打印一组现场数据。
"""

import threading

from bucketmap import ConcurrentMap, HashMap, PlainMap


def demo_hashmap():
    print("=== HashMap 单线程用法 ===")
    table = HashMap(capacity=4, load_factor=0.75)
    for i in range(6):
        table.put("key-%d" % i, i)
    print("  写入 6 个键：capacity=%d size=%d" % (table.capacity, len(table)))
    print("  get/delete/delete/get ->", table.get("key-3"), table.delete("key-3"),
          table.delete("key-3"), table.get("key-3"))
    print("  items ->", sorted(table.items()))


def demo_resize():
    print("=== ConcurrentMap 观察一次扩容 ===")
    steps = []
    m = ConcurrentMap(capacity=4, load_factor=0.75, batch=1,
                      step_hook=lambda done, total: steps.append((done, total)))
    for i in range(5):
        m.put("k%d" % i, i)
    while m.stats()["pending_buckets"]:
        m.put("k0", m.get("k0"))      # 后续写把剩下的桶分批推完
    st = m.stats()
    print("  迁移回调：", steps)
    print("  resizes=%d migrated_buckets=%d pending_buckets=%d" %
          (st["resizes"], st["migrated_buckets"], st["pending_buckets"]))
    print("  tables_live=%d entries=%d size=%d" %
          (st["tables_live"], st["entries"], st["size"]))
    print("  读到：", [m.get("k%d" % i) for i in range(5)])


def demo_threads():
    print("=== 多线程读写 ===")
    m = ConcurrentMap(capacity=8, load_factor=0.75)
    errors = []

    def worker(base):
        try:
            for i in range(200):
                m.put("t%d-k%d" % (base, i), i)
                m.get("t%d-k%d" % (base, i // 2))
                if i % 7 == 0:
                    m.delete("t%d-k%d" % (base, i))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    st = m.stats()
    print("  len(map)=%d errors=%d max_pause_ms=%.3f" %
          (len(m), len(errors), st["max_pause_ms"]))
    print("  tables_live=%d entries=%d size=%d" %
          (st["tables_live"], st["entries"], st["size"]))


def demo_reference():
    print("=== dict 参考实现 ===")
    ref = PlainMap()
    ref.put("a", 1)
    ref.put("b", 2)
    ref.delete("a")
    print("  PlainMap：len=%d items=%s" % (len(ref), sorted(ref.items())))


if __name__ == "__main__":
    for step in (demo_hashmap, demo_resize, demo_threads, demo_reference):
        step()
        print()
