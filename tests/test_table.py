"""HashMap 单线程行为的锁定测试。"""

import unittest

from bucketmap.table import HashMap


class TestBasics(unittest.TestCase):
    def test_put_get_delete_roundtrip(self):
        table = HashMap(capacity=8)
        self.assertIsNone(table.put("a", 1))
        self.assertEqual(table.put("a", 2), 1)
        self.assertEqual(table.get("a"), 2)
        self.assertEqual(len(table), 1)
        self.assertTrue(table.delete("a"))
        self.assertFalse(table.delete("a"))
        self.assertIsNone(table.get("a"))
        self.assertEqual(table.get("a", "缺"), "缺")

    def test_items_and_keys_after_delete(self):
        table = HashMap(capacity=4)
        for key, value in [("a", 1), ("b", 2), ("c", 3)]:
            table.put(key, value)
        self.assertEqual(sorted(table.items()), [("a", 1), ("b", 2), ("c", 3)])
        self.assertTrue(table.delete("b"))
        self.assertEqual(sorted(table.items()), [("a", 1), ("c", 3)])
        self.assertEqual(sorted(table.keys()), ["a", "c"])

    def test_bucket_index_points_at_the_key(self):
        table = HashMap(capacity=8)
        table.put("abc", 1)
        index = table.bucket_index("abc")
        self.assertTrue(any(k == "abc" for k, _v in table.buckets[index]))

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            HashMap(capacity=0)
        with self.assertRaises(ValueError):
            HashMap(load_factor=0)
        with self.assertRaises(ValueError):
            HashMap().put("a", None)


class TestGrowth(unittest.TestCase):
    def test_grow_doubles_and_preserves(self):
        table = HashMap(capacity=4, load_factor=0.75)
        for i in range(3):
            table.put("k%d" % i, i)
        self.assertEqual(table.capacity, 4)
        table.put("k3", 3)
        self.assertEqual(table.capacity, 8)
        self.assertEqual(len(table), 4)
        for i in range(4):
            self.assertEqual(table.get("k%d" % i), i)

    def test_no_grow_when_disabled(self):
        table = HashMap(capacity=4, load_factor=0.75, auto_grow=False)
        for i in range(10):
            table.put("k%d" % i, i)
        self.assertEqual(table.capacity, 4)
        self.assertEqual(len(table), 10)

    def test_growth_preserves_everything(self):
        table = HashMap(capacity=2, load_factor=0.75)
        for i in range(50):
            table.put("key-%d" % i, i * 10)
        self.assertEqual(len(table), 50)
        for i in range(50):
            self.assertEqual(table.get("key-%d" % i), i * 10)
        self.assertGreaterEqual(table.capacity, 64)


if __name__ == "__main__":
    unittest.main()
