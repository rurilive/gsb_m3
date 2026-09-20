"""MVCC 事务语义测试：写冲突、快照隔离、gc 后活跃快照读。

并发场景统一用 threading.Event 给两个线程的事务定节奏，避免时序靠猜。
"""

import json
import os
import tempfile
import threading
import unittest

from mvstore.store import ConflictError, Store


def wait(event, timeout=5):
    assert event.wait(timeout), "event timed out"


class TestMVCCBasics(unittest.TestCase):
    def test_snapshot_commit_basic(self):
        s = Store()
        s.put("k", 1)
        tx = s.begin()
        tx.put("k", 2)
        self.assertEqual(tx.get("k"), 2)
        self.assertEqual(s.get("k"), 1)
        tx.commit()
        self.assertEqual(s.get("k"), 2)

    def test_rollback_discards_buffer(self):
        s = Store()
        s.put("k", 1)
        tx = s.begin()
        tx.put("k", 2)
        tx.delete("other")
        tx.rollback()
        self.assertEqual(s.get("k"), 1)
        with self.assertRaises(RuntimeError):
            tx.put("k", 3)
        self.assertEqual(s._global_version, 1)

    def test_delete_conflict_and_tombstone(self):
        s = Store()
        s.put("k", 1)
        t1 = s.begin()
        t2 = s.begin()
        self.assertTrue(t2.delete("k"))
        t2.commit()
        t1.put("k", 9)
        with self.assertRaises(ConflictError):
            t1.commit()
        self.assertIsNone(s.get("k"))
        with self.assertRaises(RuntimeError):
            t1.put("k", 10)

    def test_independent_keys_commit(self):
        s = Store()
        t1 = s.begin()
        t2 = s.begin()
        t1.put("a", 1)
        t2.put("b", 2)
        t1.commit()
        t2.commit()
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_gc_no_active_keeps_latest_only(self):
        s = Store()
        s.put("k", 1)
        s.put("k", 2)
        s.put("k", 3)
        self.assertEqual(len(s._history["k"]), 3)
        s.gc()
        self.assertEqual(len(s._history["k"]), 1)
        self.assertEqual(s.get("k"), 3)

    def test_commit_appends_json_lines_and_replays(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tx.log")
            s = Store(path)
            s.put("k", 0)
            tx = s.begin()
            tx.put("k", 1)
            tx.put("m", "中文")
            tx.commit()
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            self.assertEqual([r["op"] for r in lines], ["put", "put", "put"])
            self.assertEqual(lines[1]["version"], lines[2]["version"])
            s2 = Store(path)
            self.assertEqual(s2.get("k"), 1)
            self.assertEqual(s2.get("m"), "中文")


class TestMVCCConcurrent(unittest.TestCase):
    def test_write_conflict_first_committer_wins(self):
        s = Store()
        s.put("counter", 0)
        errors = []
        t1_started = threading.Event()
        t2_began = threading.Event()
        t2_buffered = threading.Event()
        t1_committed = threading.Event()

        def tx1():
            tx = s.begin()
            t1_started.set()
            wait(t2_began)
            wait(t2_buffered)
            tx.put("counter", tx.get("counter") + 1)
            tx.commit()
            t1_committed.set()

        def tx2():
            wait(t1_started)
            tx = s.begin()
            t2_began.set()
            tx.put("counter", tx.get("counter") + 10)
            t2_buffered.set()
            wait(t1_committed)
            try:
                tx.commit()
            except ConflictError as exc:
                errors.append(exc)

        th1 = threading.Thread(target=tx1)
        th2 = threading.Thread(target=tx2)
        th1.start()
        th2.start()
        th1.join(5)
        th2.join(5)
        self.assertFalse(th1.is_alive())
        self.assertFalse(th2.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertEqual(s.get("counter"), 1)

    def test_snapshot_isolation_across_concurrent_commit(self):
        s = Store()
        s.put("k", "v0")
        reader_began = threading.Event()
        writer_committed = threading.Event()
        reader_done = threading.Event()
        reads = {}

        def reader():
            tx = s.begin()
            reader_began.set()
            reads["before"] = tx.get("k")
            wait(writer_committed)
            reads["after"] = tx.get("k")
            reader_done.set()

        def writer():
            wait(reader_began)
            tx = s.begin()
            tx.put("k", "v1")
            tx.commit()
            writer_committed.set()
            wait(reader_done)

        th_r = threading.Thread(target=reader)
        th_w = threading.Thread(target=writer)
        th_r.start()
        th_w.start()
        th_r.join(5)
        th_w.join(5)
        self.assertFalse(th_r.is_alive())
        self.assertFalse(th_w.is_alive())
        self.assertEqual(reads["before"], "v0")
        self.assertEqual(reads["after"], "v0")
        self.assertEqual(s.get("k"), "v1")

    def test_active_snapshot_read_after_gc(self):
        s = Store()
        s.put("k", "v0")
        reader_began = threading.Event()
        gc_done = threading.Event()
        reader_result = {}

        def reader():
            tx = s.begin()
            self.assertEqual(tx.snapshot_version, 1)
            reader_began.set()
            wait(gc_done)
            reader_result["old"] = tx.get("k")
            reader_result["new_key"] = tx.get("fresh")
            tx.rollback()

        def writer():
            wait(reader_began)
            s.put("k", "v1")
            s.put("k", "v2")
            s.put("fresh", "born")
            s.gc()
            self.assertEqual(
                [e["value"] for e in s._history["k"]], ["v0", "v2"]
            )
            self.assertEqual(
                [e["value"] for e in s._history["fresh"]], ["born"]
            )
            gc_done.set()

        th_r = threading.Thread(target=reader)
        th_w = threading.Thread(target=writer)
        th_r.start()
        th_w.start()
        th_r.join(5)
        th_w.join(5)
        self.assertFalse(th_r.is_alive())
        self.assertFalse(th_w.is_alive())
        self.assertEqual(reader_result["old"], "v0")
        self.assertIsNone(reader_result["new_key"])
        self.assertEqual(s.get("k"), "v2")
        self.assertEqual(s.get("fresh"), "born")


if __name__ == "__main__":
    unittest.main()
