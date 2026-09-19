"""MVCC 事务语义测试：写冲突、快照隔离、gc 与活跃快照。

用 threading.Event 给两个线程的事务定节奏，保证交错顺序确定。
"""

import threading
import unittest

from mvstore.store import ConflictError, Store


class TestMVCC(unittest.TestCase):
    def test_write_conflict_first_committer_wins(self):
        s = Store()
        s.put("k", 0)
        t1_began = threading.Event()
        t2_committed = threading.Event()
        errors = []

        def w1():
            tx = s.begin()
            tx.get("k")
            t1_began.set()
            t2_committed.wait(5)
            tx.put("k", "t1")
            try:
                tx.commit()
            except ConflictError as e:
                errors.append(e)

        def w2():
            t1_began.wait(5)
            tx = s.begin()
            tx.put("k", "t2")
            tx.commit()
            t2_committed.set()

        th1 = threading.Thread(target=w1)
        th2 = threading.Thread(target=w2)
        th1.start()
        th2.start()
        th1.join()
        th2.join()

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConflictError)
        self.assertEqual(s.get("k"), "t2")

    def test_snapshot_isolation(self):
        s = Store()
        s.put("k", "v0")
        reader_began = threading.Event()
        writer_done = threading.Event()
        seen = []

        def reader():
            tx = s.begin()
            reader_began.set()
            writer_done.wait(5)
            seen.append(tx.get("k"))
            tx.rollback()

        def writer():
            reader_began.wait(5)
            tx = s.begin()
            tx.put("k", "v1")
            tx.commit()
            writer_done.set()

        th1 = threading.Thread(target=reader)
        th2 = threading.Thread(target=writer)
        th1.start()
        th2.start()
        th1.join()
        th2.join()

        self.assertEqual(seen, ["v0"])
        self.assertEqual(s.get("k"), "v1")

    def test_read_own_writes_and_rollback(self):
        s = Store()
        s.put("k", "v0")
        tx = s.begin()
        tx.put("k", "v1")
        self.assertEqual(tx.get("k"), "v1")
        self.assertEqual(s.get("k"), "v0")
        tx.rollback()
        self.assertEqual(s.get("k"), "v0")

    def test_gc_keeps_active_snapshot_readable(self):
        s = Store()
        s.put("k", "v0")
        tx_old = s.begin()
        s.put("k", "v1")
        s.put("k", "v2")
        s.gc()
        self.assertEqual(tx_old.get("k"), "v0")
        tx_old.rollback()
        s.gc()
        self.assertEqual([v for v, _ in s._versions["k"]], [s._version])
        self.assertEqual(s.get("k"), "v2")

    def test_commit_advances_global_version(self):
        s = Store()
        base = s._version
        tx = s.begin()
        tx.put("a", 1)
        tx.commit()
        self.assertEqual(s._version, base + 1)
        self.assertEqual(s._key_version["a"], s._version)


if __name__ == "__main__":
    unittest.main()
