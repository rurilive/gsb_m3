"""KVStore / Transaction 现有行为的锁定测试。

这份文件是行为基线：现有能跑通的行为在这里钉死，改动不许破坏它。
"""

import unittest

from txnkit.store import ConflictError, KVStore, Transaction


class TestKVStore(unittest.TestCase):
    def test_set_then_get(self):
        s = KVStore()
        s.set("a", 1)
        self.assertEqual(s.get("a"), 1)

    def test_get_missing_returns_default(self):
        s = KVStore()
        self.assertIsNone(s.get("nope"))
        self.assertEqual(s.get("nope", 42), 42)

    def test_initial_data(self):
        s = KVStore({"a": 1, "b": 2})
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_delete(self):
        s = KVStore({"a": 1})
        self.assertTrue(s.delete("a"))
        self.assertFalse(s.delete("a"))
        self.assertIsNone(s.get("a"))

    def test_keys(self):
        s = KVStore({"a": 1})
        s.set("b", 2)
        self.assertEqual(sorted(s.keys()), ["a", "b"])

    def test_snapshot_is_detached_from_store(self):
        s = KVStore({"a": 1})
        snap = s.snapshot()
        snap["a"] = 99
        self.assertEqual(s.get("a"), 1)

    def test_begin_returns_transaction(self):
        s = KVStore()
        self.assertIsInstance(s.begin(), Transaction)


class TestTransaction(unittest.TestCase):
    def test_commit_makes_write_visible(self):
        s = KVStore()
        t = s.begin()
        t.set("a", 1)
        t.commit()
        self.assertEqual(s.get("a"), 1)

    def test_transaction_reads_committed_data(self):
        s = KVStore({"a": 1})
        t = s.begin()
        self.assertEqual(t.get("a"), 1)
        self.assertIsNone(t.get("zzz"))
        self.assertEqual(t.get("zzz", 7), 7)

    def test_rollback_restores_overwritten_value(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.rollback()
        self.assertEqual(s.get("a"), 1)

    def test_rollback_discards_new_key(self):
        s = KVStore()
        t = s.begin()
        t.set("n", 1)
        t.rollback()
        self.assertIsNone(s.get("n"))

    def test_commit_of_delete(self):
        s = KVStore({"a": 1, "b": 2})
        t = s.begin()
        t.delete("a")
        t.commit()
        self.assertIsNone(s.get("a"))

    def test_set_then_delete_in_same_transaction(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.delete("a")
        t.commit()
        self.assertIsNone(s.get("a"))

    def test_transaction_closed_after_commit(self):
        s = KVStore()
        t = s.begin()
        t.commit()
        with self.assertRaises(RuntimeError):
            t.commit()
        with self.assertRaises(RuntimeError):
            t.rollback()
        with self.assertRaises(RuntimeError):
            t.set("x", 1)

    def test_transaction_closed_after_rollback(self):
        s = KVStore()
        t = s.begin()
        t.rollback()
        with self.assertRaises(RuntimeError):
            t.commit()

    def test_conflict_error_is_a_runtime_error(self):
        self.assertTrue(issubclass(ConflictError, RuntimeError))


if __name__ == "__main__":
    unittest.main()
