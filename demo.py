"""ConcurrentHashMap 现状演示。

第一段：单锁哈希表的写入、查找、删除与计数。
第二段：预留的分段锁与迁移演示位子（见文末注释）。
"""

from shardmap.hashmap import ConcurrentHashMap


def main():
    print("=== 单锁哈希表 ===")
    m = ConcurrentHashMap(4)
    for i in range(5):
        m.put(i, i * i)
    print(f"  put 0..4 -> size={m.size}")
    print(f"  get(3)      = {m.get(3)}")
    print(f"  get(99)     = {m.get(99)}")
    print(f"  delete(1)   = {m.delete(1)} size={m.size}")
    print(f"  contains(1) = {m.contains(1)}")
    print(f"  keys        = {sorted(m.keys())}")
    print(f"  depth       = {m.depth}")

    # TODO(分段锁与渐进迁移): ShardedHashMap 实现后，在这里加一段演示：
    # 注入随机种子与假时钟，造若干分段各自持锁并发读写，
    # 驱动一次 rehash 看迁移期间读写仍然正确、迁移完成后各分段到新表，
    # 以及并行度等于分段数。


if __name__ == "__main__":
    main()
