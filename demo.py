"""cachely 现状演示。

第一段：无界字典缓存的写入与读回、命中与未命中、访问计数。
第二段：预留的容量与淘汰策略演示位子（见文末注释）。
"""

from cachely import DictCache


def main():
    print("=== 无界字典读写 ===")
    c = DictCache()
    c.set("alpha", 1)
    c.set("beta", 2)
    c.set("gamma", 3)
    print("  命中 alpha:", c.get("alpha"))
    print("  未命中 delta:", c.get("delta"))
    print("  alpha 访问计数:", c.access_count("alpha"))
    print("  beta 访问计数:", c.access_count("beta"))
    print("  条目数:", len(c))

    # TODO(淘汰策略改造): LRU 与 LFU 的容量受限缓存、TTL 过期、容量与统计、
    # 并发安全就位后，在这里补一遍演示：先造一个 LRU 缓存塞满容量看最久未
    # 使用项被挤掉，再造一个 LFU 缓存看频次最低项被淘汰，打印命中、未命中、
    # 淘汰次数与被驱逐的键。


if __name__ == "__main__":
    main()
