"""shardmap 现状演示。

第一段：单字典映射 FlatMap 的读写。
第二段：预留的分片并发演示位子（见文末注释）。
"""

from shardmap.map import FlatMap


def main():
    print("=== 基线：单字典映射 ===")
    m = FlatMap()
    m.set("user-1", "alice")
    m.set("user-2", "bob")
    m.set("user-3", "carol")
    print("  user-1 ->", m.get("user-1"))
    print("  user-2 ->", m.get("user-2"))
    print("  缺失键 ->", m.get("user-404"))
    print("  键数 ->", len(m))
    m.set("user-1", "alice-v2")
    print("  覆盖后 user-1 ->", m.get("user-1"))

    # TODO(分片并发改造): 实现分片、细粒度锁、原子操作、快照与重分片后，
    # 在这里加一段演示：分片读写与键的落片查询、并发读改写后计数不丢、
    # 取一致快照并稳定遍历、增加分片数重分片后键值一致。


if __name__ == "__main__":
    main()
