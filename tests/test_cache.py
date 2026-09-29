"""FifoCache 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：定容写入与读回、满时按插入先后淘汰、
peek 不改变状态、keys 的插入序、以及容量非正数的报错口径。
新增行为（最少频次淘汰、频次桶、平局口径等）另建测试文件，
本文件一个字都不许改，且必须保持全绿。
"""

import unittest

from lfux.cache import FifoCache


class TestPutGet(unittest.TestCase):
    def test_get_missing_returns_none(self):
        c = FifoCache(2)
        self.assertIsNone(c.get("absent"))

    def test_put_then_get(self):
        c = FifoCache(2)
        self.assertEqual(c.put("a", 1), 1)
        self.assertEqual(c.get("a"), 1)

    def test_put_overwrites_value(self):
        c = FifoCache(2)
        c.put("a", 1)
        c.put("a", 2)
        self.assertEqual(c.get("a"), 2)
        self.assertEqual(len(c), 1)

    def test_len_and_contains(self):
        c = FifoCache(3)
        self.assertEqual(len(c), 0)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(len(c), 2)
        self.assertIn("a", c)
        self.assertNotIn("z", c)


class TestCapacityValidation(unittest.TestCase):
    def test_zero_cap_raises(self):
        with self.assertRaises(ValueError):
            FifoCache(0)

    def test_negative_cap_raises(self):
        with self.assertRaises(ValueError):
            FifoCache(-1)


class TestFifoEviction(unittest.TestCase):
    def test_never_exceeds_capacity(self):
        c = FifoCache(3)
        for i in range(10):
            c.put("k%d" % i, i)
        self.assertEqual(len(c), 3)

    def test_evicts_earliest_inserted(self):
        c = FifoCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)

    def test_access_does_not_protect_entry(self):
        c = FifoCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.get("a")
        c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)

    def test_keys_in_insertion_order(self):
        c = FifoCache(3)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertEqual(c.keys(), ["a", "b", "c"])

    def test_overwrite_keeps_insertion_position(self):
        c = FifoCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 9)
        c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(c.keys(), ["b", "c"])


class TestPeek(unittest.TestCase):
    def test_peek_returns_value(self):
        c = FifoCache(2)
        c.put("a", 1)
        self.assertEqual(c.peek("a"), 1)

    def test_peek_missing_returns_none(self):
        c = FifoCache(2)
        self.assertIsNone(c.peek("absent"))

    def test_peek_does_not_change_state(self):
        c = FifoCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.peek("a")
        c.peek("a")
        c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.keys(), ["b", "c"])


if __name__ == "__main__":
    unittest.main()
