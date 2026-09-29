"""DictStore 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：写通落盘、命中和未命中的返回形态、覆盖写、
删除、按键列出与快照、后端写次数逐条累计，以及成员与长度判断。新增行为
（内存缓冲、合并、刷盘策略、读穿、脏项计数、幂等重放与崩溃丢缓冲）另建
测试文件，不改动本文件。
"""

import unittest

from wbuf.store import DictStore


class TestGetPut(unittest.TestCase):
    def test_miss_returns_false_none(self):
        store = DictStore()
        self.assertEqual(store.get("absent"), (False, None))

    def test_put_then_get_hit(self):
        store = DictStore()
        self.assertEqual(store.put("a", 1), 1)
        self.assertEqual(store.get("a"), (True, 1))

    def test_put_overwrites_value(self):
        store = DictStore()
        store.put("a", 1)
        store.put("a", 2)
        self.assertEqual(store.get("a"), (True, 2))
        self.assertEqual(len(store), 1)

    def test_put_is_write_through(self):
        store = DictStore()
        store.put("a", 1)
        self.assertEqual(store.get("a"), (True, 1))
        self.assertEqual(store.backend_writes(), 1)


class TestDelete(unittest.TestCase):
    def test_delete_existing_returns_true(self):
        store = DictStore()
        store.put("a", 1)
        self.assertTrue(store.delete("a"))

    def test_delete_missing_returns_false(self):
        store = DictStore()
        self.assertFalse(store.delete("absent"))

    def test_deleted_key_reads_missing(self):
        store = DictStore()
        store.put("a", 1)
        store.delete("a")
        self.assertEqual(store.get("a"), (False, None))


class TestKeysAndDump(unittest.TestCase):
    def test_keys_sorted(self):
        store = DictStore()
        store.put("c", 3)
        store.put("a", 1)
        store.put("b", 2)
        self.assertEqual(store.keys(), ["a", "b", "c"])

    def test_dump_snapshot_sorted(self):
        store = DictStore()
        store.put("b", 2)
        store.put("a", 1)
        self.assertEqual(store.dump(), {"a": 1, "b": 2})

    def test_contains(self):
        store = DictStore()
        store.put("a", 1)
        self.assertIn("a", store)
        self.assertNotIn("b", store)


class TestWriteCounter(unittest.TestCase):
    def test_backend_writes_accumulate(self):
        store = DictStore()
        store.put("a", 1)
        store.put("b", 2)
        self.assertEqual(store.backend_writes(), 2)

    def test_overwrite_counts_as_write(self):
        store = DictStore()
        store.put("a", 1)
        store.put("a", 2)
        self.assertEqual(store.backend_writes(), 2)

    def test_delete_does_not_count_as_write(self):
        store = DictStore()
        store.put("a", 1)
        store.delete("a")
        self.assertEqual(store.backend_writes(), 1)


if __name__ == "__main__":
    unittest.main()