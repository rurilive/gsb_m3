"""MVStore 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：put 返回提交时间戳、get 取当前可见版本、
delete 写墓碑、keys 与 latest_ts。新增行为（快照读、版本可见性、写冲突、
回收、历史查询）另开测试文件，不改动本文件。
"""

import unittest

from mvvault.store import MVStore, Version


class TestPutAndGet(unittest.TestCase):
    def test_put_returns_increasing_timestamp(self):
        store = MVStore()
        self.assertEqual(store.put("a", 1), 1)
        self.assertEqual(store.put("a", 2), 2)
        self.assertEqual(store.latest_ts, 2)

    def test_get_returns_latest_value(self):
        store = MVStore()
        store.put("a", 1)
        store.put("a", 2)
        self.assertEqual(store.get("a"), 2)

    def test_get_missing_key_is_none(self):
        store = MVStore()
        self.assertIsNone(store.get("nope"))

    def test_value_object_is_same_instance(self):
        store = MVStore()
        obj = {"n": 1}
        store.put("a", obj)
        self.assertIs(store.get("a"), obj)


class TestDelete(unittest.TestCase):
    def test_delete_returns_whether_existed(self):
        store = MVStore()
        store.put("a", 1)
        self.assertTrue(store.delete("a"))
        self.assertFalse(store.delete("a"))

    def test_get_after_delete_is_none(self):
        store = MVStore()
        store.put("a", 1)
        store.delete("a")
        self.assertIsNone(store.get("a"))

    def test_delete_appends_tombstone_version(self):
        store = MVStore()
        store.put("a", 1)
        store.delete("a")
        versions = store._versions["a"]
        self.assertEqual(len(versions), 2)
        self.assertTrue(versions[-1].deleted)

    def test_rewrite_after_delete(self):
        store = MVStore()
        store.put("a", 1)
        store.delete("a")
        store.put("a", 9)
        self.assertEqual(store.get("a"), 9)


class TestKeys(unittest.TestCase):
    def test_keys_are_sorted_and_live(self):
        store = MVStore()
        store.put("b", 1)
        store.put("a", 1)
        store.put("c", 1)
        store.delete("a")
        self.assertEqual(store.keys(), ["b", "c"])

    def test_empty_store(self):
        store = MVStore()
        self.assertEqual(store.keys(), [])
        self.assertEqual(store.latest_ts, 0)


class TestVersionChain(unittest.TestCase):
    def test_versions_are_ts_ordered(self):
        store = MVStore()
        for i in range(4):
            store.put("a", i)
        self.assertEqual([v.ts for v in store._versions["a"]], [1, 2, 3, 4])

    def test_version_namedtuple_fields(self):
        version = Version(3, "x", False)
        self.assertEqual(version.ts, 3)
        self.assertEqual(version.value, "x")
        self.assertFalse(version.deleted)


if __name__ == "__main__":
    unittest.main()