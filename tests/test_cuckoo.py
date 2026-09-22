"""CuckooFilter 行为测试：可删、零假阴性、扩容重排、误判率、落盘。"""

import random
import time
import unittest

from crawlkit import CuckooFilter
from crawlkit.hashing import fingerprint, hash_pair


def _same_fp_disjoint_pair(fp_bits=12, capacity=100):
    """找一对指纹相同、桶对互不相交且各自独立落位的键。"""
    probe = CuckooFilter(capacity=capacity, fp_bits=fp_bits)
    num_buckets = probe.num_buckets
    mask = num_buckets - 1
    seen = {}
    for i in range(200000):
        key = "probe-%d" % i
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, fp_bits)
        i1 = h1 & mask
        i2 = probe._alt_bucket(i1, fp, num_buckets)
        pair = frozenset((i1, i2))
        prev = seen.get(fp)
        if prev is not None and prev[0].isdisjoint(pair):
            return prev[1], key
        seen.setdefault(fp, (pair, key))
    raise RuntimeError("probe space exhausted")


class TestCuckooBasics(unittest.TestCase):
    def test_added_keys_always_hit(self):
        cf = CuckooFilter(capacity=100)
        keys = ["u%d" % i for i in range(100)]
        for k in keys:
            cf.add(k)
        for k in keys:
            self.assertIn(k, cf)

    def test_len_counts_adds(self):
        cf = CuckooFilter(capacity=10)
        cf.add("a")
        cf.add("b")
        self.assertEqual(len(cf), 2)

    def test_bad_args_rejected(self):
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=17)

    def test_remove_missing_returns_false(self):
        cf = CuckooFilter(capacity=10)
        self.assertFalse(cf.remove("nope"))

    def test_stats_is_fresh_dict(self):
        cf = CuckooFilter(capacity=10)
        s = cf.stats()
        s["added"] = 99
        self.assertEqual(cf.stats()["added"], 0)

    def test_remove_then_readd(self):
        cf = CuckooFilter(capacity=10)
        cf.add("a")
        self.assertTrue(cf.remove("a"))
        self.assertNotIn("a", cf)
        cf.add("a")
        self.assertIn("a", cf)


class TestCuckooRemoveIsolation(unittest.TestCase):
    def test_removed_key_misses_peer_survives(self):
        # 同指纹、桶对互不相交：删一个，另一个必须照常命中
        x, y = _same_fp_disjoint_pair()
        cf = CuckooFilter(capacity=100, fp_bits=12)
        cf.add(x)
        cf.add(y)
        self.assertIn(x, cf)
        self.assertIn(y, cf)
        self.assertTrue(cf.remove(x))
        self.assertNotIn(x, cf)
        self.assertIn(y, cf)

    def test_remove_does_not_touch_other_keys(self):
        cf = CuckooFilter(capacity=500, fp_bits=12)
        keys = ["k%d" % i for i in range(500)]
        for k in keys:
            cf.add(k)
        for k in keys[::37]:
            cf.remove(k)
        for k in keys:
            if int(k[1:]) % 37 == 0:
                self.assertNotIn(k, cf)
            else:
                self.assertIn(k, cf)

    def test_remove_is_exact_by_origin(self):
        # 同指纹、桶对相同但归属不同的两个键各自占独立槽；删一个只清
        # 它自己那条，另一条原封不动（计数为证），还能被精确查询命中。
        fp_bits = 12
        a = b = None
        seen = {}
        for i in range(2000000):
            key = "col-%d" % i
            h1, h2 = hash_pair(key)
            fp = fingerprint(h2, fp_bits)
            sig = (fp, h1 & 0xFFFFF)
            if sig in seen and seen[sig][1] != h1:
                a, a_h1 = seen[sig][0], seen[sig][1]
                b, b_h1 = key, h1
                break
            seen.setdefault(sig, (key, h1))
        if b is None:
            self.skipTest("no crafted collision found")
        cf = CuckooFilter(capacity=40000, fp_bits=fp_bits)
        cf.add(a)
        cf.add(b)
        self.assertEqual(len(cf), 2)
        self.assertTrue(cf.remove(a))
        self.assertEqual(len(cf), 1)
        # b 的条目还在它自己的归属位上（精确比对，不是假阳性）
        mask = cf.num_buckets - 1
        _, b_h2 = hash_pair(b)
        fb = fingerprint(b_h2, fp_bits)
        origin_b = b_h1 & cf._origin_mask
        i1 = b_h1 & mask
        i2 = cf._alt_bucket(i1, fb, cf.num_buckets)
        found_exact = False
        for bucket in (i1, i2):
            for slot in range(bucket * 4, bucket * 4 + 4):
                entry = cf._table[slot]
                if (
                    entry
                    and (entry & cf._fp_mask) == fb
                    and entry >> fp_bits == origin_b
                ):
                    found_exact = True
        self.assertTrue(found_exact)


class TestCuckooResize(unittest.TestCase):
    def test_forced_growth_never_false_negative(self):
        cf = CuckooFilter(capacity=4, fp_bits=6)
        keys = ["g%05d" % i for i in range(600)]
        start_buckets = cf.num_buckets
        for n, k in enumerate(keys, 1):
            cf.add(k)
            for j in range(n):
                self.assertIn(keys[j], cf)
        self.assertGreaterEqual(cf.num_buckets, start_buckets * 16)

    def test_resize_is_chain_not_recursion(self):
        # 链再长也不许递归：add/grow/rebuild 里都不能出现自调用
        import inspect

        from crawlkit import cuckoo as mod

        for name in ("add", "_grow", "_rebuild", "_place"):
            src = inspect.getsource(getattr(mod.CuckooFilter, name))
            self.assertNotIn("self.%s(" % name, src)


class TestCuckooRandomStress(unittest.TestCase):
    def test_set_oracle_add_remove_query(self):
        rng = random.Random(20260922)
        cf = CuckooFilter(capacity=20000, fp_bits=12)
        oracle = set()
        keys = ["s%06d" % i for i in range(12000)]
        for _ in range(60000):
            k = keys[rng.randrange(len(keys))]
            r = rng.random()
            if r < 0.45:
                cf.add(k)
                oracle.add(k)
            elif r < 0.8:
                if k in oracle:
                    self.assertIn(k, cf)
            else:
                if k in oracle:
                    self.assertTrue(cf.remove(k))
                    oracle.discard(k)
                if k in oracle:
                    self.assertIn(k, cf)
        missing = [k for k in oracle if k not in cf]
        self.assertEqual(missing, [])


class TestCuckooFPRAndPerf(unittest.TestCase):
    def test_fp_rate_under_two_per_mille(self):
        rng = random.Random(4242)
        n = 100000
        cf = CuckooFilter(capacity=n, fp_bits=12)
        keys = ["r%012x" % rng.getrandbits(64) for _ in range(n)]
        for k in keys:
            cf.add(k)
        for k in keys:
            self.assertIn(k, cf)
        trials = 200000
        false_pos = sum(
            ("r%012x" % rng.getrandbits(64)) in cf for _ in range(trials)
        )
        self.assertLess(false_pos / trials, 0.002)

    def test_hundred_k_mixed_ops_under_six_seconds(self):
        rng = random.Random(7)
        cf = CuckooFilter(capacity=20000, fp_bits=12)
        live = set()
        start = time.time()
        for _ in range(100000):
            k = "p%d" % rng.randrange(40000)
            r = rng.random()
            if r < 0.45:
                cf.add(k)
                live.add(k)
            elif r < 0.8:
                if k in live:
                    self.assertIn(k, cf)
            elif k in live:
                cf.remove(k)
                live.discard(k)
        elapsed = time.time() - start
        missing = [k for k in live if k not in cf]
        self.assertEqual(missing, [])
        self.assertLess(elapsed, 6.0)

    def test_heap_same_order_as_bloom(self):
        from crawlkit.bloom import BloomFilter

        n = 100000
        ck = CuckooFilter(capacity=n, fp_bits=12)
        bf = BloomFilter(capacity=n, fp_rate=0.01)
        # 装载堆高不许掉量级：cuckoo 不得比 bloom 大一个数量级以上
        self.assertLess(ck.stats()["size_bytes"], bf.stats()["size_bytes"] * 10)


class TestCuckooRoundTrip(unittest.TestCase):
    def test_round_trip_byte_identical(self):
        cf = CuckooFilter(capacity=100, fp_bits=12)
        for i in range(60):
            cf.add("k%d" % i)
        cf.remove("k3")
        blob = cf.to_bytes()
        back = CuckooFilter.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.capacity, cf.capacity)
        self.assertEqual(back.fp_bits, cf.fp_bits)
        self.assertEqual(len(back), len(cf))

    def test_round_trip_hits_misses_and_fps(self):
        cf = CuckooFilter(capacity=300, fp_bits=10)
        for i in range(200):
            cf.add("in%d" % i)
        for i in range(0, 200, 4):
            cf.remove("in%d" % i)
        back = CuckooFilter.from_bytes(cf.to_bytes())
        for i in range(200):
            k = "in%d" % i
            self.assertEqual(k in back, k in cf)
        for i in range(5000):
            q = "out%d" % i
            self.assertEqual(q in back, q in cf)

    def test_round_trip_after_growth(self):
        cf = CuckooFilter(capacity=4, fp_bits=6)
        for i in range(300):
            cf.add("g%04d" % i)
        back = CuckooFilter.from_bytes(cf.to_bytes())
        self.assertEqual(back.num_buckets, cf.num_buckets)
        for i in range(300):
            self.assertIn("g%04d" % i, back)

    def test_bad_magic_rejected(self):
        blob = bytearray(CuckooFilter(capacity=10).to_bytes())
        blob[0:4] = b"NOPE"
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(bytes(blob))

    def test_truncated_rejected(self):
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(b"short")

    def test_payload_length_checked(self):
        blob = CuckooFilter(capacity=10).to_bytes()
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(blob[:-1])

    def test_non_power_of_two_buckets_rejected(self):
        cf = CuckooFilter(capacity=10)
        blob = bytearray(cf.to_bytes())
        # num_buckets 字段偏移 8（magic 后第一个 uint32）
        blob[8:12] = (7).to_bytes(4, "big")
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(bytes(blob))


if __name__ == "__main__":
    unittest.main()
