"""leasekv 现有增量行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from leasekv.kv import LeaseKV


class TestLeaseKV(unittest.TestCase):
    def test_put_and_get(self):
        kv = LeaseKV()
        kv.put("a", {"n": 1})
        self.assertEqual(kv.get("a"), {"n": 1})

    def test_get_returns_copy(self):
        kv = LeaseKV()
        kv.put("a", {"n": 1})
        out = kv.get("a")
        out["n"] = 99
        self.assertEqual(kv.get("a"), {"n": 1})

    def test_put_copies_value(self):
        kv = LeaseKV()
        source = {"n": 1}
        kv.put("a", source)
        source["n"] = 99
        self.assertEqual(kv.get("a"), {"n": 1})

    def test_get_missing_returns_default(self):
        kv = LeaseKV()
        self.assertIsNone(kv.get("nope"))
        self.assertEqual(kv.get("nope", 7), 7)

    def test_overwrite_keeps_position(self):
        kv = LeaseKV()
        kv.put("a", 1)
        kv.put("b", 2)
        kv.put("c", 3)
        kv.put("a", 9)
        self.assertEqual(kv.keys(), ("a", "b", "c"))
        self.assertEqual(kv.get("a"), 9)

    def test_delete_hit_and_miss(self):
        kv = LeaseKV()
        kv.put("a", 1)
        self.assertTrue(kv.delete("a"))
        self.assertFalse(kv.delete("a"))
        self.assertEqual(kv.keys(), ())

    def test_contains(self):
        kv = LeaseKV()
        kv.put("a", 1)
        self.assertTrue(kv.contains("a"))
        self.assertFalse(kv.contains("b"))

    def test_stats_hits_and_misses(self):
        kv = LeaseKV()
        kv.put("a", 1)
        kv.get("a")
        kv.get("a")
        kv.get("missing")
        s = kv.stats()
        self.assertEqual(s["live"], 1)
        self.assertEqual(s["hits"], 2)
        self.assertEqual(s["misses"], 1)

    def test_stats_returns_fresh_dict(self):
        kv = LeaseKV()
        s = kv.stats()
        s["live"] = 99
        self.assertEqual(kv.stats()["live"], 0)

    def test_len(self):
        kv = LeaseKV()
        self.assertEqual(len(kv), 0)
        kv.put("a", 1)
        kv.put("b", 2)
        self.assertEqual(len(kv), 2)

    def test_empty_key_rejected(self):
        kv = LeaseKV()
        with self.assertRaises(ValueError):
            kv.put("", 1)

    def test_non_string_key_rejected(self):
        kv = LeaseKV()
        with self.assertRaises(ValueError):
            kv.put(1, 1)

    def test_none_value_rejected(self):
        kv = LeaseKV()
        with self.assertRaises(ValueError):
            kv.put("a", None)

    def test_get_non_string_key_rejected(self):
        kv = LeaseKV()
        with self.assertRaises(ValueError):
            kv.get(3)

    def test_delete_non_string_key_rejected(self):
        kv = LeaseKV()
        with self.assertRaises(ValueError):
            kv.delete(3)


if __name__ == "__main__":
    unittest.main()