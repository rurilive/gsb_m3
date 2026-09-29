"""ConcurrentHashMap 现有行为的锁定测试。"""

import threading
import unittest

from shardmap.hashmap import ConcurrentHashMap


class TestConcurrentHashMap(unittest.TestCase):
    def test_new_map_is_empty(self):
        m = ConcurrentHashMap()
        self.assertEqual(m.size, 0)
        self.assertEqual(m.keys(), [])
        self.assertEqual(m.items(), [])

    def test_put_returns_true_for_new_key(self):
        m = ConcurrentHashMap()
        self.assertTrue(m.put("a", 1))
        self.assertEqual(m.size, 1)

    def test_put_returns_false_when_overwriting(self):
        m = ConcurrentHashMap()
        m.put("a", 1)
        self.assertFalse(m.put("a", 2))
        self.assertEqual(m.size, 1)
        self.assertEqual(m.get("a"), 2)

    def test_get_missing_returns_default(self):
        m = ConcurrentHashMap()
        self.assertIsNone(m.get("nope"))
        self.assertEqual(m.get("nope", 7), 7)

    def test_get_returns_stored_value(self):
        m = ConcurrentHashMap()
        m.put(10, "ten")
        self.assertEqual(m.get(10), "ten")

    def test_delete_existing(self):
        m = ConcurrentHashMap()
        m.put("a", 1)
        self.assertTrue(m.delete("a"))
        self.assertEqual(m.size, 0)
        self.assertFalse(m.contains("a"))

    def test_delete_missing_returns_false(self):
        m = ConcurrentHashMap()
        self.assertFalse(m.delete("ghost"))
        self.assertEqual(m.size, 0)

    def test_size_tracks_puts_and_deletes(self):
        m = ConcurrentHashMap()
        for i in range(5):
            m.put(i, i * i)
        self.assertEqual(m.size, 5)
        m.delete(2)
        self.assertEqual(m.size, 4)

    def test_contains(self):
        m = ConcurrentHashMap()
        m.put("k", 1)
        self.assertTrue(m.contains("k"))
        self.assertFalse(m.contains("v"))

    def test_keys_and_items_snapshot(self):
        m = ConcurrentHashMap()
        m.put("a", 1)
        m.put("b", 2)
        self.assertEqual(sorted(m.keys()), ["a", "b"])
        self.assertEqual(sorted(m.items()), [("a", 1), ("b", 2)])

    def test_keys_reflects_deletion(self):
        m = ConcurrentHashMap()
        m.put("a", 1)
        m.put("b", 2)
        m.delete("a")
        self.assertEqual(m.keys(), ["b"])

    def test_reuse_after_delete(self):
        m = ConcurrentHashMap()
        m.put("a", 1)
        m.delete("a")
        self.assertTrue(m.put("a", 9))
        self.assertEqual(m.get("a"), 9)
        self.assertEqual(m.size, 1)

    def test_custom_hash_fn_used(self):
        seen = []

        def h(key):
            seen.append(key)
            return 0

        m = ConcurrentHashMap(4, hash_fn=h)
        m.put("z", 1)
        self.assertEqual(m.get("z"), 1)
        self.assertIn("z", seen)

    def test_clock_is_injectable(self):
        m = ConcurrentHashMap(4, clock=lambda: 5.0)
        m.put("a", 1)
        self.assertEqual(m.get("a"), 1)

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            ConcurrentHashMap(0)

    def test_depth_is_one(self):
        m = ConcurrentHashMap()
        self.assertEqual(m.depth, 1)

    def test_many_keys_keep_consistent(self):
        m = ConcurrentHashMap(4)
        for i in range(200):
            m.put(i, i)
        self.assertEqual(m.size, 200)
        for i in range(0, 200, 3):
            m.delete(i)
        expected = 200 - len(range(0, 200, 3))
        self.assertEqual(m.size, expected)
        for i in range(200):
            if i % 3 == 0:
                self.assertFalse(m.contains(i))
            else:
                self.assertEqual(m.get(i), i)

    def test_concurrent_puts_are_counted(self):
        m = ConcurrentHashMap(8)
        threads = []
        for t in range(4):
            def worker(base=t):
                for i in range(50):
                    m.put(base * 1000 + i, i)
            th = threading.Thread(target=worker)
            threads.append(th)
        for th in threads:
            th.start()
        for th in threads:
            th.join(5)
        self.assertEqual(m.size, 200)


if __name__ == "__main__":
    unittest.main()
