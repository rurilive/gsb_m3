"""事务隔离性的回归测试。

钉住联调中暴露的五类现象：
1. 事务内能读到自己刚写的值（read-your-writes）；
2. 提交落地的值与调用方手里的可变对象互不共享；
3. rollback 能恢复事务内被删的键；
4. 两个事务先后提交按逐键合并，后提交不顶掉整张表；
5. 事务开始后被别的事务改过的键判冲突，提交整体作废。
另含快照隔离与冲突键报告的细化测试。
"""

import unittest

from txnkit.store import ConflictError, KVStore


class TestReadYourWrites(unittest.TestCase):
    def test_set_then_get_returns_new_value(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        self.assertEqual(t.get("a"), 2)
        t.commit()
        self.assertEqual(s.get("a"), 2)

    def test_set_new_key_then_get(self):
        s = KVStore()
        t = s.begin()
        t.set("n", {"x": 1})
        self.assertEqual(t.get("n"), {"x": 1})
        t.commit()

    def test_delete_then_get_returns_default(self):
        s = KVStore({"a": 1})
        t = s.begin()
        self.assertTrue(t.delete("a"))
        self.assertIsNone(t.get("a"))
        self.assertEqual(t.get("a", 42), 42)

    def test_delete_then_set_reads_new_value(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.delete("a")
        t.set("a", 9)
        self.assertEqual(t.get("a"), 9)
        t.commit()
        self.assertEqual(s.get("a"), 9)

    def test_set_then_delete_hides_key(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.delete("a")
        self.assertIsNone(t.get("a"))
        t.rollback()
        self.assertEqual(s.get("a"), 1)

    def test_reads_snapshot_not_concurrent_commits(self):
        s = KVStore({"a": 1})
        t1 = s.begin()
        t2 = s.begin()
        t2.set("a", 2)
        t2.commit()
        self.assertEqual(t1.get("a"), 1)


class TestValueOwnership(unittest.TestCase):
    def test_set_detaches_nested_value_before_commit(self):
        s = KVStore()
        t = s.begin()
        cfg = {"tags": ["a"]}
        t.set("cfg", cfg)
        cfg["tags"].append("b")
        self.assertEqual(t.get("cfg"), {"tags": ["a"]})
        t.commit()
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})

    def test_committed_value_detached_from_caller(self):
        s = KVStore()
        t = s.begin()
        cfg = {"tags": ["a"]}
        t.set("cfg", cfg)
        t.commit()
        cfg["tags"].append("b")
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})

    def test_get_returns_detached_copy(self):
        s = KVStore()
        s.set("cfg", {"tags": ["a"]})
        out = s.get("cfg")
        out["tags"].append("b")
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})

        t = s.begin()
        inside = t.get("cfg")
        inside["tags"].append("c")
        self.assertEqual(t.get("cfg"), {"tags": ["a"]})
        t.rollback()

    def test_initial_data_is_detached(self):
        initial = {"cfg": {"tags": ["a"]}}
        s = KVStore(initial)
        initial["cfg"]["tags"].append("b")
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})

    def test_transaction_does_not_touch_store_before_commit(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.set("n", 3)
        t.delete("a")
        self.assertEqual(s.get("a"), 1)
        self.assertIsNone(s.get("n"))


class TestRollback(unittest.TestCase):
    def test_rollback_restores_deleted_key(self):
        s = KVStore({"a": 1, "b": 2})
        t = s.begin()
        t.delete("a")
        t.rollback()
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_rollback_restores_overwritten_value(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.rollback()
        self.assertEqual(s.get("a"), 1)

    def test_rollback_discards_all_changes(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.set("a", 2)
        t.set("n", 3)
        t.delete("a")
        t.rollback()
        self.assertEqual(s.get("a"), 1)
        self.assertIsNone(s.get("n"))
        self.assertEqual(sorted(s.keys()), ["a"])

    def test_delete_missing_key_returns_false(self):
        s = KVStore()
        t = s.begin()
        self.assertFalse(t.delete("ghost"))
        t.rollback()


class TestMergeCommit(unittest.TestCase):
    def test_sequential_transactions_merge_key_by_key(self):
        s = KVStore()
        t1 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2 = s.begin()
        t2.set("b", 2)
        t2.commit()
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)
        self.assertEqual(sorted(s.keys()), ["a", "b"])

    def test_concurrent_transactions_disjoint_keys_both_commit(self):
        s = KVStore({"a": 1, "b": 2})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 10)
        t2.set("b", 20)
        t1.commit()
        t2.commit()
        self.assertEqual(s.get("a"), 10)
        self.assertEqual(s.get("b"), 20)

    def test_commit_deletes_and_merges(self):
        s = KVStore({"a": 1, "b": 2})
        t = s.begin()
        t.delete("a")
        t.set("c", 3)
        t.commit()
        self.assertIsNone(s.get("a"))
        self.assertEqual(s.get("b"), 2)
        self.assertEqual(s.get("c"), 3)
        self.assertEqual(sorted(s.keys()), ["b", "c"])


class TestConflictDetection(unittest.TestCase):
    def test_overwrite_conflicts_and_changes_nothing(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.set("a", 2)
        with self.assertRaises(ConflictError) as ctx:
            t2.commit()
        self.assertEqual(ctx.exception.keys, ["a"])
        self.assertEqual(s.get("a"), 1)

    def test_delete_conflicts_with_concurrent_overwrite(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.delete("a")
        with self.assertRaises(ConflictError) as ctx:
            t2.commit()
        self.assertEqual(ctx.exception.keys, ["a"])
        self.assertEqual(s.get("a"), 1)

    def test_overwrite_conflicts_with_concurrent_delete(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.delete("a")
        t1.commit()
        t2.set("a", 1)
        with self.assertRaises(ConflictError) as ctx:
            t2.commit()
        self.assertEqual(ctx.exception.keys, ["a"])
        self.assertNotIn("a", s.keys())

    def test_conflict_reports_all_changed_keys_sorted(self):
        s = KVStore({"a": 1, "b": 2, "c": 3})
        t_other = s.begin()
        t_late = s.begin()
        t_other.set("a", 10)
        t_other.set("c", 30)
        t_other.commit()
        t_late.set("c", 31)
        t_late.set("a", 11)
        t_late.set("keep", 9)
        with self.assertRaises(ConflictError) as ctx:
            t_late.commit()
        self.assertEqual(ctx.exception.keys, ["a", "c"])
        self.assertEqual(s.get("a"), 10)
        self.assertEqual(s.get("c"), 30)
        self.assertEqual(s.get("b"), 2)
        self.assertIsNone(s.get("keep"))

    def test_failed_commit_leaves_transaction_rollbackable(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.set("a", 2)
        with self.assertRaises(ConflictError):
            t2.commit()
        t2.rollback()
        self.assertEqual(s.get("a"), 1)

    def test_read_only_txn_commits_after_concurrent_change(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        self.assertEqual(t2.get("a"), 0)
        t2.commit()
        self.assertEqual(s.get("a"), 1)


if __name__ == "__main__":
    unittest.main()
