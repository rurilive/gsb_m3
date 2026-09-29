"""HashRing 现状演示。

第一段：单点环下加节点与 lookup 的确定性，以及加节点后 key 归属的变化。
第二段：预留的虚拟节点与权重演示位子（见文末注释）。
"""

from hashring.ring import HashRing

KEYS = [f"user-{i}" for i in range(1000)]


def main():
    print("=== 基础环 ===")
    ring = HashRing()
    for node in ("node-a", "node-b", "node-c"):
        ring.add_node(node)
    before = [ring.lookup(k) for k in KEYS]
    counts = {}
    for owner in before:
        counts[owner] = counts.get(owner, 0) + 1
    for node in sorted(counts):
        print(f"  {node}: {counts[node]} keys")

    ring.add_node("node-d")
    after = [ring.lookup(k) for k in KEYS]
    moved = sum(1 for a, b in zip(before, after) if a != b)
    print(f"  加 node-d 后改归属的 key: {moved} / {len(KEYS)}")

    print("  空环 lookup ->", HashRing().lookup("any"))

    # TODO(虚拟节点与权重): 实现虚拟节点、权重与删除节点后，在这里加一段演示：
    # 同一批 key 在 vnode 数不同的环上的分布均衡度，以及删掉一个节点后
    # 实际改归属的 key 是否只落在被删节点的份额上。


if __name__ == "__main__":
    main()
