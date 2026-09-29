"""cascadectl 现状演示。

第一段：单层 LRU 的读写、命中与未命中、容量满时的淘汰。
第二段：预留的两级缓存与降级演示位子（见文末注释）。
"""

from cascadectl import LRUCache


def main():
    print("=== 单层读写 ===")
    c = LRUCache(2)
    c.put("alpha", 1)
    c.put("beta", 2)
    print("  命中 alpha:", c.get("alpha"))
    print("  未命中 gamma:", c.get("gamma"))
    print("  键（旧到新）:", c.keys())
    print("  统计:", c.stats())

    print("=== 单层淘汰 ===")
    c.get("alpha")  # alpha 变最新，beta 最久未用
    c.put("gamma", 3)  # 容量已满，淘汰 beta
    print("  beta 还在吗:", "beta" in c)
    print("  键（旧到新）:", c.keys())
    print("  统计:", c.stats())

    # TODO(两级缓存与降级): L1 热层、L2 温层、降级与提升、TTL 过期、
    # 回写队列与分层统计就位后，在这里补一遍演示：L1 满了把一条降到 L2，
    # 再从 L2 取回并按策略提升回 L1，打印两级的命中数与提升降级次数。


if __name__ == "__main__":
    main()