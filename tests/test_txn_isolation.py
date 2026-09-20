"""事务隔离性回归测试。

钉住联调时暴露的四类现象：读己之写、提交后与调用方共享嵌套结构、
回滚恢复被删的键、两个事务先后提交的逐键合并与冲突检测。
"""

import unittest

from txnkit.store import ConflictError, KVStore


class TestReadYourWrites(unittest.TestCase):
    def test_set_then_get_in_same_transaction(self):
        s = KVStore({"counter": 0})
        t = s.begin()
        t.set("counter", 1)
        self.assertEqual(t.get("counter"), 1)
        t.commit()

    def test_delete_then_get_in_same_transaction(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.delete("a")
        self.assertIsNone(t.get("a"))
        t.rollback()

    def test_delete_is_not_visible_outside_before_commit(self):
        s = KVStore({"a": 1})
        t = s.begin()
        t.delete("a")
        self.assertEqual(s.get("a"), 1)
        t.rollback()


class TestCommitDetachesValues(unittest.TestCase):
    def test_caller_mutation_after_commit_does_not_leak(self):
        s = KVStore()
        t = s.begin()
        cfg = {"tags": ["a"]}
        t.set("cfg", cfg)
        t.commit()
        cfg["tags"].append("b")
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})

    def test_caller_mutation_after_set_before_commit_does_not_leak(self):
        s = KVStore()
        t = s.begin()
        cfg = {"tags": ["a"]}
        t.set("cfg", cfg)
        cfg["tags"].append("b")
        t.commit()
        self.assertEqual(s.get("cfg"), {"tags": ["a"]})


class TestRollback(unittest.TestCase):
    def test_rollback_restores_deleted_key(self):
        s = KVStore({"a": 1, "b": 2})
        t = s.begin()
        t.delete("a")
        t.rollback()
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_rollback_leaves_other_transactions_writes_alone(self):
        s = KVStore({"a": 1})
        t1 = s.begin()
        t1.set("b", 2)
        t1.commit()
        t2 = s.begin()
        t2.set("c", 3)
        t2.rollback()
        self.assertEqual(s.get("b"), 2)
        self.assertIsNone(s.get("c"))


class TestCommitMergesPerKey(unittest.TestCase):
    def test_sequential_commits_merge_keys(self):
        s = KVStore()
        t1 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2 = s.begin()
        t2.set("b", 2)
        t2.commit()
        self.assertEqual(sorted(s.keys()), ["a", "b"])
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_overlapping_transactions_on_disjoint_keys_both_commit(self):
        s = KVStore()
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t2.set("b", 2)
        t1.commit()
        t2.commit()
        self.assertEqual(sorted(s.keys()), ["a", "b"])

    def test_conflicting_key_aborts_whole_commit(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.set("a", 2)
        t2.set("other", 9)
        with self.assertRaises(ConflictError) as ctx:
            t2.commit()
        self.assertEqual(ctx.exception.keys, ["a"])
        self.assertEqual(s.get("a"), 1)
        self.assertIsNone(s.get("other"))

    def test_conflicting_delete_aborts_commit(self):
        s = KVStore({"a": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.delete("a")
        with self.assertRaises(ConflictError):
            t2.commit()
        self.assertEqual(s.get("a"), 1)

    def test_untouched_keys_do_not_conflict(self):
        s = KVStore({"a": 0, "b": 0})
        t1 = s.begin()
        t2 = s.begin()
        t1.set("a", 1)
        t1.commit()
        t2.set("b", 2)
        t2.commit()
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)


if __name__ == "__main__":
    unittest.main()
