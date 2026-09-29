"""lfukit 现状演示。

第一段：缓存写入与命中，看次数累计与统计。
第二段：容量满时的频次淘汰，看次数最小者先出、次数相同取最久未使用。
第三段：预留的过期与衰减演示位子（见文末注释）。
"""

from lfukit import LFUCache


def main():
    print("=== 基础读写 ===")
    cache = LFUCache(capacity=3)
    cache.put("a", 1)
    cache.put("b", 2)
    print("  命中 a:", cache.get("a"))
    print("  未命中 zzz:", cache.get("zzz"))
    print("  统计:", cache.stats())

    print("=== 频次淘汰 ===")
    cache.put("c", 3)
    cache.put("d", 4)  # 容量 3 已满，b 次数最低先出
    print("  淘汰后键:", cache.keys())
    print("  b 还在吗:", "b" in cache)
    print("  统计:", cache.stats())

    # TODO(过期与衰减): 注入时钟与 decay 窗口就位后在这里补两段演示：
    # 条目写入后过 3 秒再 get 应返回 None 且 expired 加一；
    # 容量满时先清空过期条目再按衰减后的加权频次淘汰，
    # 加权频次相同则按最近使用次序，并报出命中、未命中、淘汰、过期四个指标。


if __name__ == "__main__":
    main()