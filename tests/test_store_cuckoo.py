"""DedupStore 的 cuckoo 后端：retry 真删、计数、落盘读回。"""

import unittest

from crawlkit import DedupStore


class TestCuckooStore(unittest.TestCase):
    def test_retry_removes_for_real(self):
        s = DedupStore(capacity=100, backend="cuckoo", fp_bits=12)
        s.mark("u1")
        s.mark("u2")
        self.assertTrue(s.is_duplicate("u1"))
        self.assertTrue(s.retry("u1"))
        self.assertFalse(s.is_duplicate("u1"))
        self.assertTrue(s.is_duplicate("u2"))

    def test_retry_unknown_returns_false(self):
        s = DedupStore(capacity=10, backend="cuckoo")
        self.assertFalse(s.retry("nope"))

    def test_retry_then_remark(self):
        s = DedupStore(capacity=10, backend="cuckoo")
        s.mark("u1")
        s.retry("u1")
        s.mark("u1")
        self.assertTrue(s.is_duplicate("u1"))

    def test_other_key_survives_retry(self):
        s = DedupStore(capacity=500, backend="cuckoo", fp_bits=12)
        keys = ["u%d" % i for i in range(500)]
        for k in keys:
            s.mark(k)
        for k in keys[::31]:
            s.retry(k)
        for k in keys:
            expect_dup = int(k[1:]) % 31 != 0
            self.assertEqual(s.is_duplicate(k), expect_dup)

    def test_stats_filter_is_cuckoo(self):
        s = DedupStore(capacity=100, backend="cuckoo", fp_bits=12)
        s.mark("u1")
        st = s.stats()
        self.assertEqual(st["marks"], 1)
        self.assertEqual(st["filter"]["fp_bits"], 12)
        self.assertIn("num_buckets", st["filter"])

    def test_bad_backend_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore(capacity=10, backend="redis")

    def test_round_trip(self):
        s = DedupStore(capacity=200, fp_rate=0.02, backend="cuckoo", fp_bits=12)
        for i in range(100):
            s.mark("u%d" % i)
        for i in range(0, 100, 5):
            s.retry("u%d" % i)
        s.is_duplicate("u3")
        blob = s.to_bytes()
        back = DedupStore.from_bytes(blob)
        self.assertEqual(back.backend, "cuckoo")
        self.assertEqual(back.fp_bits, 12)
        self.assertEqual(back.to_bytes(), blob)
        for i in range(100):
            expect_dup = i % 5 != 0
            self.assertEqual(back.is_duplicate("u%d" % i), expect_dup)

    def test_bloom_blob_still_loads_as_bloom(self):
        bloom = DedupStore(capacity=10)
        bloom.mark("z1")
        back = DedupStore.from_bytes(bloom.to_bytes())
        self.assertEqual(back.backend, "bloom")
        self.assertTrue(back.is_duplicate("z1"))


if __name__ == "__main__":
    unittest.main()
