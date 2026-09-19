"""MVCC 事务语义测试：写冲突、快照隔离、gc 与活跃快照共存。"""

import threading
import unittest

from mvstore.store import ConflictError, Store


class TestWriteConflict(unittest.TestCase):
    def test_first_committer_wins(self):
        s = Store()
        s.put("k", 0)

        a_written = threading.Event()
        b_written = threading.Event()
        a_committed = threading.Event()
        outcome = {}

        def txn_a():
            t = s.begin()
            t.get("k")
            t.put("k", 1)
            a_written.set()
            b_written.wait(5)
            t.commit()
            a_committed.set()

        def txn_b():
            t = s.begin()
            a_written.wait(5)
            t.get("k")
            t.put("k", 2)
            b_written.set()
            a_committed.wait(5)
            try:
                t.commit()
            except ConflictError as e:
                outcome["error"] = e

        ta = threading.Thread(target=txn_a)
        tb = threading.Thread(target=txn_b)
        ta.start()
        tb.start()
        ta.join(5)
        tb.join(5)

        self.assertFalse(ta.is_alive() or tb.is_alive())
        self.assertIsInstance(outcome.get("error"), ConflictError)
        self.assertEqual(s.get("k"), 1)

    def test_disjoint_write_sets_no_conflict(self):
        s = Store()
        s.put("x", 0)
        s.put("y", 0)
        t1 = s.begin()
        t2 = s.begin()
        t1.put("x", 1)
        t2.put("y", 2)
        t1.commit()
        t2.commit()
        self.assertEqual(s.get("x"), 1)
        self.assertEqual(s.get("y"), 2)


class TestSnapshotIsolation(unittest.TestCase):
    def test_snapshot_reads_ignore_later_commits(self):
        s = Store()
        s.put("k", "v0")

        old_seen = {}
        old_begun = threading.Event()
        new_committed = threading.Event()
        done = threading.Event()

        def reader():
            t = s.begin()
            old_begun.set()
            new_committed.wait(5)
            old_seen["value"] = t.get("k")
            t.rollback()
            done.set()

        th = threading.Thread(target=reader)
        th.start()
        old_begun.wait(5)

        t2 = s.begin()
        t2.put("k", "v1")
        t2.commit()
        new_committed.set()

        done.wait(5)
        th.join(5)
        self.assertEqual(old_seen.get("value"), "v0")
        self.assertEqual(s.get("k"), "v1")
        self.assertEqual(s.begin().get("k"), "v1")

    def test_read_own_writes(self):
        s = Store()
        s.put("k", 1)
        t = s.begin()
        t.put("k", 2)
        self.assertEqual(t.get("k"), 2)
        self.assertEqual(s.get("k"), 1)
        t.rollback()
        self.assertEqual(s.get("k"), 1)

    def test_rollback_discards_buffer(self):
        s = Store()
        s.put("k", 1)
        t = s.begin()
        t.put("k", 99)
        t.delete("k")
        t.rollback()
        self.assertEqual(s.get("k"), 1)


class TestGC(unittest.TestCase):
    def test_gc_keeps_version_visible_to_active_snapshot(self):
        s = Store()
        s.put("k", 1)
        t_old = s.begin()
        s.put("k", 2)
        s.put("k", 3)
        s.gc()
        self.assertEqual(t_old.get("k"), 1)
        self.assertEqual(s.get("k"), 3)
        t_old.rollback()

    def test_gc_without_active_txns_keeps_only_latest(self):
        s = Store()
        s.put("k", 1)
        s.put("k", 2)
        s.put("k", 3)
        s.gc()
        self.assertEqual(len(s._versions["k"]), 1)
        self.assertEqual(s.get("k"), 3)

    def test_gc_after_active_txn_ends(self):
        s = Store()
        s.put("k", 1)
        t_old = s.begin()
        s.put("k", 2)
        s.put("k", 3)
        s.gc()
        self.assertGreater(len(s._versions["k"]), 1)
        t_old.rollback()
        s.gc()
        self.assertEqual(len(s._versions["k"]), 1)
        self.assertEqual(s.get("k"), 3)

    def test_gc_drops_fully_deleted_key(self):
        s = Store()
        s.put("gone", 1)
        s.delete("gone")
        s.gc()
        self.assertNotIn("gone", s._versions)
        self.assertIsNone(s.get("gone"))

    def test_version_advances_per_commit(self):
        s = Store()
        self.assertEqual(s._version, 0)
        s.put("a", 1)
        t = s.begin()
        t.put("b", 2)
        t.commit()
        self.assertEqual(s._version, 2)
        t2 = s.begin()
        t2.put("c", 3)
        t2.rollback()
        self.assertEqual(s._version, 2)


if __name__ == "__main__":
    unittest.main()
