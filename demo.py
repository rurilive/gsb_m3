"""crawlkit 现状演示。

第一段：布隆过滤器加键、查键，看统计。
第二段：DedupStore 门面走一遍标记与判重，顺带认一遍落盘读回。
第三段：预留的布谷鸟过滤器演示位子（见文末注释）。
"""

from crawlkit import BloomFilter, CuckooFilter, DedupStore
from crawlkit.hashing import fingerprint, hash_pair


def _same_fp_pair(fp_bits):
    """蛮力找两个指纹相同的键，演示同指纹互不影响。"""
    by_fp = {}
    i = 0
    while True:
        key = "demo-twin-%d" % i
        fp = fingerprint(hash_pair(key)[1], fp_bits)
        if fp in by_fp:
            return by_fp[fp], key
        by_fp[fp] = key
        i += 1


def main():
    print("=== 布隆过滤器 ===")
    bf = BloomFilter(capacity=1000, fp_rate=0.01)
    for i in range(5):
        bf.add("https://example.com/page%d" % i)
    print("  已加 page0 命中:", "https://example.com/page0" in bf)
    print("  未加 never 命中:", "https://example.com/never" in bf)
    print("  stats:", bf.stats())

    print("=== DedupStore ===")
    store = DedupStore(capacity=1000)
    store.mark("https://example.com/a")
    print("  is_duplicate(a):", store.is_duplicate("https://example.com/a"))
    print("  is_duplicate(b):", store.is_duplicate("https://example.com/b"))
    blob = store.to_bytes()
    back = DedupStore.from_bytes(blob)
    print("  落盘 %d 字节，读回后 is_duplicate(a): %s" % (
        len(blob), back.is_duplicate("https://example.com/a")))
    print("  stats:", store.stats())

    print("=== 布谷鸟过滤器（可撤销的重试）===")
    store = DedupStore(capacity=1000, backend="cuckoo")
    store.mark("https://example.com/x")
    store.mark("https://example.com/y")
    print("  mark 后 is_duplicate(x):", store.is_duplicate("https://example.com/x"))
    store.retry("https://example.com/x")
    print("  retry(x) 后 is_duplicate(x):", store.is_duplicate("https://example.com/x"))
    print("  retry(x) 后 is_duplicate(y):", store.is_duplicate("https://example.com/y"))

    # 同指纹的两个键：撤掉一个，另一个照常命中
    while True:
        k1, k2 = _same_fp_pair(8)
        cf = CuckooFilter(capacity=64, fp_bits=8)
        cf.add(k1)
        cf.add(k2)
        cf.remove(k1)
        if k2 in cf and k1 not in cf:
            break
    print("  同指纹键 %r / %r: 撤掉 k1 后 k1 命中: %s, k2 命中: %s" % (
        k1, k2, k1 in cf, k2 in cf))

    # 踢出链超限触发扩容，扩容前后查询结果一致
    small = CuckooFilter(capacity=8, fp_bits=12)
    keys = ["https://example.com/g%d" % i for i in range(200)]
    before = small.stats()["num_buckets"]
    for k in keys:
        small.add(k)
    after = small.stats()["num_buckets"]
    print("  扩容: num_buckets %d -> %d, 200 个键全部命中: %s" % (
        before, after, all(k in small for k in keys)))

    blob = store.to_bytes()
    back = DedupStore.from_bytes(blob)
    print("  落盘 %d 字节读回: is_duplicate(y)=%s, is_duplicate(x)=%s" % (
        len(blob),
        back.is_duplicate("https://example.com/y"),
        back.is_duplicate("https://example.com/x")))


if __name__ == "__main__":
    main()
