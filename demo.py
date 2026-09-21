"""BPlusTree 现状演示。

第一段：写入 200 个键，看分裂次数与树高。
第二段：范围扫描顺着叶子链走，以及惰性迭代。
第三段：删掉大半，看借用、合并与节点池回收。
文末留了并发演示的位子。
"""

import random

from ordix import BPlusTree


def main():
    print("=== 写入与分裂 ===")
    t = BPlusTree(min_degree=3)
    keys = list(range(200))
    random.Random(1).shuffle(keys)
    for k in keys:
        t.put(k, k * 10)
    s = t.stats()
    print("  size=%d height=%d splits=%d" % (len(t), t.height(), s["splits"]))
    print("  get(123) -> %r" % (t.get(123),))
    print("  get(999) -> %r" % (t.get(999),))

    print("=== 范围扫描 ===")
    got = list(t.scan(40, 44))
    print("  scan(40, 44) -> %r" % (got,))
    it = t.scan(45)
    print("  惰性取三个：%r" % ([next(it) for _ in range(3)],))

    print("=== 删除与节点回收 ===")
    for k in range(150):
        t.delete(k)
    s = t.stats()
    p = t.pool_stats()
    print("  size=%d height=%d merges=%d borrows=%d" % (
        len(t), t.height(), s["merges"], s["borrows"]))
    print("  剩余最小 5 个键：%r" % ([k for k, _ in t.scan(150, 155)],))
    print("  pool live=%d free=%d" % (p["live"], p["free"]))
    for k in range(150):
        t.put(k, k * 10)
    p = t.pool_stats()
    print("  写回 150 个键后 pool live=%d reused=%d created=%d" % (
        p["live"], p["reused"], p["created"]))
    t.validate()
    print("  validate() 通过")

    # TODO(并发改造): 并发版本落地后，在这里加一段演示：多个读线程
    # 一边 get 一边范围扫描，写线程同时增删，先跑出吞吐数字，再和
    # 单线程基线对比；并发跑完之后打印 pool_stats，看 live 有没有
    # 落回稳态、闩锁顺序约定在 README 里是怎么写的。


if __name__ == "__main__":
    main()
