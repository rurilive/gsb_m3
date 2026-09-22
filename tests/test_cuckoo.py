"""CuckooFilter 与 DedupStore cuckoo 后端的行为测试。"""

import random
import sys
import time
import unittest

from crawlkit import CuckooFilter, DedupStore, NotSupportedError
from crawlkit.cuckoo import _mix64
from crawlkit.hashing import fingerprint, hash_pair


def same_fp_pair(fp_bits, num_buckets):
    """找两个指纹相同、候选桶不重叠的键，让撤一个查不到、另一个照常命中。"""
    mask = num_buckets - 1
    by_fp = {}
    i = 0
    while True:
        key = "twin-%d" % i
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, fp_bits)
        i1 = h1 & mask
        buckets = {i1, i1 ^ (_mix64(fp) & mask)}
        for other_fp, (other_key, other_buckets) in by_fp.items():
            if other_fp == fp and not buckets & other_buckets:
                return other_key, key
        by_fp.setdefault(fp, (key, buckets))
        i += 1


class TestCuckooFilter(unittest.TestCase):
    def test_added_keys_always_hit(self):
        cf = CuckooFilter(capacity=500)
        keys = ["u%d" % i for i in range(500)]
        for k in keys:
            self.assertTrue(cf.add(k))
        for k in keys:
            self.assertIn(k, cf)

    def test_missing_keys_mostly_miss(self):
        cf = CuckooFilter(capacity=500, fp_bits=12)
        for i in range(500):
            cf.add("in-%d" % i)
        misses = sum(1 for i in range(2000) if ("out-%d" % i) not in cf)
        self.assertGreater(misses, 1900)

    def test_len_counts_distinct_keys(self):
        cf = CuckooFilter(capacity=10)
        self.assertTrue(cf.add("a"))
        self.assertFalse(cf.add("a"))
        self.assertEqual(len(cf), 1)

    def test_remove_gone_others_stay(self):
        cf = CuckooFilter(capacity=100)
        keys = ["r%d" % i for i in range(50)]
        for k in keys:
            cf.add(k)
        for k in keys[::2]:
            self.assertTrue(cf.remove(k))
        for i, k in enumerate(keys):
            if i % 2 == 0:
                self.assertNotIn(k, cf)
            else:
                self.assertIn(k, cf)
        self.assertEqual(len(cf), 25)
        self.assertFalse(cf.remove("never-added"))
        self.assertFalse(cf.remove(keys[0]))

    def test_remove_leaves_same_fp_sibling(self):
        cf = CuckooFilter(capacity=64, fp_bits=8)
        k1, k2 = same_fp_pair(8, cf.stats()["num_buckets"])
        cf.add(k1)
        cf.add(k2)
        self.assertTrue(cf.remove(k1))
        self.assertNotIn(k1, cf)
        self.assertIn(k2, cf)

    def test_growth_never_loses_keys(self):
        cf = CuckooFilter(capacity=8, fp_bits=12)
        keys = ["g%d" % i for i in range(600)]
        added = []
        for k in keys:
            cf.add(k)
            added.append(k)
            for old in added:
                self.assertIn(old, cf)
        self.assertGreater(cf.stats()["num_buckets"], 8)

    def test_growth_without_recursion(self):
        depth = 0
        frame = sys._getframe()
        while frame is not None:
            depth += 1
            frame = frame.f_back
        cf = CuckooFilter(capacity=8, fp_bits=12)
        keys = ["nr-%d" % i for i in range(600)]
        sys.setrecursionlimit(depth + 40)
        try:
            for k in keys:
                cf.add(k)
        finally:
            sys.setrecursionlimit(1000)
        for k in keys:
            self.assertIn(k, cf)

    def test_false_positive_rate(self):
        rng = random.Random(20260922)
        cf = CuckooFilter(capacity=100000, fp_bits=12)
        added = ["%032x" % rng.getrandbits(128) for _ in range(100000)]
        for k in added:
            cf.add(k)
        for k in added[::997]:
            self.assertIn(k, cf)
        probes = ["%032x" % rng.getrandbits(128) for _ in range(100000)]
        hits = sum(1 for k in probes if k in cf)
        self.assertLessEqual(hits / len(probes), 0.002)

    def test_stress_matches_set(self):
        rng = random.Random(147)
        cf = CuckooFilter(capacity=4096, fp_bits=12)
        live = set()
        keys = ["sk-%d" % i for i in range(20000)]
        start = time.monotonic()
        for _ in range(100000):
            key = keys[rng.randrange(len(keys))]
            op = rng.random()
            if op < 0.45:
                self.assertEqual(cf.add(key), key not in live)
                live.add(key)
            elif op < 0.70:
                self.assertEqual(cf.remove(key), key in live)
                live.discard(key)
            elif key in live:
                self.assertIn(key, cf)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 6.0)
        for key in live:
            self.assertIn(key, cf)

    def test_round_trip_byte_identical_and_same_behavior(self):
        cf = CuckooFilter(capacity=256, fp_bits=12)
        keys = ["rt-%d" % i for i in range(200)]
        for k in keys:
            cf.add(k)
        for k in keys[::4]:
            cf.remove(k)
        blob = cf.to_bytes()
        back = CuckooFilter.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.capacity, cf.capacity)
        self.assertEqual(back.fp_bits, cf.fp_bits)
        self.assertEqual(len(back), len(cf))
        self.assertEqual(back.stats(), cf.stats())
        for i in range(2000):
            q = "q-%d" % i
            self.assertEqual(q in back, q in cf)
        # 读回来还能接着加、接着删、接着扩容
        for i in range(2000):
            back.add("more-%d" % i)
        for i in range(2000):
            self.assertIn("more-%d" % i, back)
        self.assertTrue(back.remove("more-0"))
        self.assertNotIn("more-0", back)

    def test_stats_is_fresh_dict(self):
        cf = CuckooFilter(capacity=10)
        st = cf.stats()
        st["added"] = 99
        self.assertEqual(cf.stats()["added"], 0)

    def test_bad_params_rejected(self):
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=-3)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=33)

    def test_bad_blob_rejected(self):
        blob = bytearray(CuckooFilter(capacity=10).to_bytes())
        blob[0:4] = b"NOPE"
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(bytes(blob))
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(b"short")
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(CuckooFilter(capacity=10).to_bytes()[:-1])


class TestDedupStoreCuckoo(unittest.TestCase):
    def test_mark_retry_flow(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        s.mark("u1")
        s.mark("u2")
        self.assertTrue(s.is_duplicate("u1"))
        self.assertTrue(s.retry("u1"))
        self.assertFalse(s.is_duplicate("u1"))
        self.assertTrue(s.is_duplicate("u2"))
        self.assertFalse(s.retry("u1"))
        self.assertFalse(s.retry("never-marked"))

    def test_retry_after_remark(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        s.mark("u1")
        s.retry("u1")
        s.mark("u1")
        self.assertTrue(s.is_duplicate("u1"))

    def test_stats_report_backend(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        st = s.stats()
        self.assertEqual(st["backend"], "cuckoo")
        self.assertIn("fp_bits", st["filter"])
        bloom = DedupStore(capacity=100)
        self.assertEqual(bloom.stats()["backend"], "bloom")
        with self.assertRaises(NotSupportedError):
            bloom.retry("u1")

    def test_round_trip(self):
        s = DedupStore(capacity=50, fp_rate=0.02, backend="cuckoo")
        for i in range(10):
            s.mark("u%d" % i)
        s.retry("u5")
        s.is_duplicate("u0")
        blob = s.to_bytes()
        back = DedupStore.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.backend, "cuckoo")
        self.assertEqual(back.capacity, s.capacity)
        self.assertEqual(back.fp_rate, s.fp_rate)
        self.assertEqual(back.stats()["marks"], 10)
        self.assertTrue(back.is_duplicate("u3"))
        self.assertFalse(back.is_duplicate("u5"))
        # 读回来还能接着撤
        self.assertTrue(back.retry("u3"))
        self.assertFalse(back.is_duplicate("u3"))

    def test_unknown_backend_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore(capacity=10, backend="trie")

    def test_bad_fp_rate_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore(capacity=10, fp_rate=1.5, backend="cuckoo")


if __name__ == "__main__":
    unittest.main()
