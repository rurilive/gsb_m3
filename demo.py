"""crawlkit 现状演示。

第一段：布隆过滤器加键、查键，看统计。
第二段：DedupStore 门面走一遍标记与判重，顺带认一遍落盘读回。
第三段：布谷鸟过滤器可删、同指纹不连坐、踢出扩容零假阴性、落盘读回。
"""

from crawlkit import BloomFilter, CuckooFilter, DedupStore
from crawlkit.hashing import fingerprint, hash_pair


def _same_fingerprint_pair(fp_bits=12):
    """找一对指纹相同且桶对互不相交的键，用来验证删除不连坐。"""
    seen = {}
    i = 0
    while True:
        key = "fp-probe-%d" % i
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, fp_bits)
        if fp in seen:
            other = seen[fp]
            probe = CuckooFilter(capacity=100, fp_bits=fp_bits)
            probe.add(other)
            probe.add(key)
            if len(probe) == 2:
                probe.remove(other)
                if key in probe and other not in probe:
                    return other, key
        else:
            seen[fp] = key
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

    print("=== 布谷鸟过滤器：删除与重试 ===")
    cuckoo = DedupStore(capacity=1000, backend="cuckoo", fp_bits=12)
    cuckoo.mark("https://example.com/a")
    cuckoo.mark("https://example.com/b")
    print("  撤前 is_duplicate(a):", cuckoo.is_duplicate("https://example.com/a"))
    cuckoo.retry("https://example.com/a")
    print("  retry(a) 后 is_duplicate(a):", cuckoo.is_duplicate("https://example.com/a"))
    print("  同批的 b 不受影响:", cuckoo.is_duplicate("https://example.com/b"))

    key_x, key_y = _same_fingerprint_pair()
    cf = CuckooFilter(capacity=100, fp_bits=12)
    cf.add(key_x)
    cf.add(key_y)
    print("  同指纹两键都在:", key_x in cf, key_y in cf)
    cf.remove(key_x)
    print("  remove 前者后：前者命中=%s，后者命中=%s" % (key_x in cf, key_y in cf))

    print("=== 布谷鸟过滤器：踢出链触发扩容，全程无假阴性 ===")
    small = CuckooFilter(capacity=4, fp_bits=6)
    grown_before = small.num_buckets
    keys = ["grow-%04d" % i for i in range(400)]
    for n, k in enumerate(keys, 1):
        small.add(k)
        # 死线：此刻起所有已加键都必须命中，扩容重排也不例外
        assert all(("grow-%04d" % j) in small for j in range(n))
    print("  桶数 %d -> %d，%d 个已加键全部命中" % (
        grown_before, small.num_buckets, len(keys)))
    blob = small.to_bytes()
    back_cf = CuckooFilter.from_bytes(blob)
    print("  落盘 %d 字节读回，命中数: %d，stats: %s" % (
        len(blob), sum(k in back_cf for k in keys), back_cf.stats()))


if __name__ == "__main__":
    main()
