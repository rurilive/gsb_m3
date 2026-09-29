"""hashring 现状演示。

第一段：取模分片器下几个 key 的归属，以及加一个节点后大面积改归属的现象。
第二段：预留的一致性哈希改造演示位子（见文末注释）。
"""

from hashring.ring import ModShard

KEYS = [f"user-{i}" for i in range(1000)]


def main():
    print("=== 取模分片 ===")
    shard = ModShard()
    for node in ("node-a", "node-b", "node-c"):
        shard.add_node(node)
    before = [shard.owner(k) for k in KEYS]
    counts = {}
    for owner in before:
        counts[owner] = counts.get(owner, 0) + 1
    for node in sorted(counts):
        print(f"  {node}: {counts[node]} keys")

    shard.add_node("node-d")
    after = [shard.owner(k) for k in KEYS]
    moved = sum(1 for a, b in zip(before, after) if a != b)
    print(f"  加 node-d 后改归属的 key: {moved} / {len(KEYS)}")

    for key in ("user-0", "user-1", "user-2"):
        print(f"  {key} -> {shard.owner(key)}")

    print("  空分片器 owner ->", ModShard().owner("any"))

    # TODO(一致性哈希改造): 把 ModShard 扩成能上生产的一致性哈希环之后，
    # 在这里补第二段演示：增删一个节点，打印实际迁移的 key 数并与取模口径对比，
    # 再看清只有被增删节点那一小段区间内的 key 改了归属。


if __name__ == "__main__":
    main()
