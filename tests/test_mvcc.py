"""MVCC 事务语义测试。

双线程场景用 threading.Event 定节奏，确保交错顺序确定：
两个事务先各自 begin 拿到同一快照，再交错读写、提交。
"""

import json
import os
import tempfile
import threading
import unittest

from mvstore.store import ConflictError, Store


class TestMvcc(unittest.TestCase):
    def test_write_conflict_first_committer_wins(self):
        # 两线程事务 begin 于同一版本，写同一 key：先提交者生效，
        # 后提交者抛 ConflictError，其写入整体作废。
        store = Store()
        store.put("counter", 0)

        t1_started = threading.Event()
        t2_started = threading.Event()
        t1_committed = threading.Event()
        t2_done = threading.Event()
        errors = []
        txns = {}

        def txn1():
            txn = store.begin()
            t1_started.set()
            t2_started.wait(5)
            txn.put("counter", txn.get("counter") + 1)
            txn.commit()
            t1_committed.set()

        def txn2():
            txn = store.begin()
            txns["t2"] = txn
            t2_started.set()
            t1_started.wait(5)
            # 等 txn1 先提交，本事务的快照仍停留在更早版本。
            t1_committed.wait(5)
            txn.put("counter", txn.get("counter") + 10)
            try:
                txn.commit()
            except ConflictError as exc:
                errors.append(exc)
            t2_done.set()

        threads = [
            threading.Thread(target=txn1),
            threading.Thread(target=txn2),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertTrue(t2_done.wait(1))

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].key, "counter")
        self.assertEqual(store.get("counter"), 1)
        # 冲突事务已作废，再次提交或写入必须被拒绝。
        with self.assertRaises(RuntimeError):
            txns["t2"].put("counter", 99)
        with self.assertRaises(RuntimeError):
            txns["t2"].commit()

    def test_snapshot_isolation_and_disjoint_commits(self):
        # 同一快照开启的两个事务：各自只看到 begin 时的状态与自己的缓冲；
        # 写集不相交时两者都能提交，随后的新事务能看到全部结果。
        store = Store()
        store.put("a", 1)

        t1_started = threading.Event()
        t2_started = threading.Event()
        t1_committed = threading.Event()
        t2_done = threading.Event()
        results = {}

        def txn1():
            txn = store.begin()
            t1_started.set()
            t2_started.wait(5)
            txn.put("a", txn.get("a") + 1)
            txn.put("b", "from-t1")
            # 事务内可见自己的缓冲。
            results["t1_own_b"] = txn.get("b")
            txn.commit()
            t1_committed.set()

        def txn2():
            txn = store.begin()
            t2_started.set()
            t1_started.wait(5)
            t1_committed.wait(5)
            # 快照不包含 txn1 的提交。
            results["t2_snapshot_a"] = txn.get("a")
            self.assertIsNone(txn.get("b"))
            # 自己的缓冲也可见。
            txn.put("c", "from-t2")
            results["t2_own_c"] = txn.get("c")
            txn.commit()  # 写集只有 c，与 txn1 不相交，不冲突
            t2_done.set()

        threads = [
            threading.Thread(target=txn1),
            threading.Thread(target=txn2),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertTrue(t2_done.wait(1))

        self.assertEqual(results["t1_own_b"], "from-t1")
        self.assertEqual(results["t2_snapshot_a"], 1)
        self.assertEqual(results["t2_own_c"], "from-t2")

        after = store.begin()
        self.assertEqual(after.get("a"), 2)
        self.assertEqual(after.get("b"), "from-t1")
        self.assertEqual(after.get("c"), "from-t2")
        after.rollback()

    def test_gc_preserves_active_snapshot_reads(self):
        # 旧事务仍活跃时 gc 不能回收其快照需要的版本；
        # 事务结束后再次 gc，每个 key 只保留最新版本。
        store = Store()
        store.put("k", "v0")

        reader_ready = threading.Event()
        writer_done = threading.Event()
        reader_done = threading.Event()
        seen = {}

        def reader():
            txn = store.begin()
            self.assertEqual(txn.get("k"), "v0")
            reader_ready.set()
            writer_done.wait(5)
            # k 在旧快照之后被改过两次，本事务读出来仍必须是 v0。
            store.gc()
            seen["old"] = txn.get("k")
            txn.rollback()
            reader_done.set()

        def writer():
            reader_ready.wait(5)
            t1 = store.begin()
            t1.put("k", "v1")
            t1.commit()
            t2 = store.begin()
            t2.put("k", "v2")
            t2.commit()
            writer_done.set()

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertTrue(reader_done.wait(1))

        self.assertEqual(seen["old"], "v0")
        self.assertEqual(store.get("k"), "v2")
        # 活跃快照保留下，v0/v1/v2 三个版本都在。
        # reader 已结束，此刻无活跃事务：gc 后只剩最新版。
        store.gc()
        self.assertEqual(len(store._versions["k"]), 1)
        self.assertEqual(store._versions["k"][0][1], "v2")

    def test_gc_with_no_active_transactions_keeps_latest(self):
        store = Store()
        store.put("k", 1)
        store.put("k", 2)
        t = store.begin()
        t.delete("k")
        t.commit()
        store.gc()
        self.assertEqual(len(store._versions["k"]), 1)
        self.assertIsNone(store.get("k"))

    def test_gc_keeps_last_entry_visible_to_oldest_snapshot(self):
        # key 在最老快照之后没有新提交时，gc 不能把它唯一的旧版本
        # 当成"版本号小于 floor"删掉，否则快照读者会读出 None。
        store = Store()
        store.put("old", "v0")          # v0
        reader = store.begin()          # 快照 v0
        store.put("other", 1)           # v1，未碰 old
        store.gc()
        self.assertEqual(reader.get("old"), "v0")
        self.assertEqual(len(store._versions["old"]), 1)
        reader.rollback()

        store.put("hot", "a")           # v2
        slow = store.begin()            # 快照 v2
        store.put("hot", "b")           # v3
        store.put("hot", "c")           # v4
        store.gc()
        # 快照 v2 需要的 v2 与更新的 v3/v4 都必须保留。
        self.assertEqual(slow.get("hot"), "a")
        self.assertEqual(
            [entry[1] for entry in store._versions["hot"]], ["c", "b", "a"]
        )
        slow.rollback()

    def test_rollback_discards_buffer(self):
        store = Store()
        store.put("k", "committed")
        txn = store.begin()
        txn.put("k", "uncommitted")
        txn.put("new", "x")
        self.assertEqual(txn.get("k"), "uncommitted")
        txn.rollback()
        self.assertEqual(store.get("k"), "committed")
        self.assertIsNone(store.get("new"))
        # 作废后再次 rollback 是 no-op，commit/读写应报错。
        txn.rollback()
        with self.assertRaises(RuntimeError):
            txn.commit()
        with self.assertRaises(RuntimeError):
            txn.get("k")

    def test_conflict_aborts_and_allows_retry(self):
        store = Store()
        store.put("k", 0)
        t1 = store.begin()
        t2 = store.begin()
        t1.put("k", 1)
        t1.commit()
        t2.put("k", 2)
        with self.assertRaises(ConflictError) as cm:
            t2.commit()
        self.assertEqual(cm.exception.key, "k")
        with self.assertRaises(RuntimeError):
            t2.put("k", 3)
        self.assertEqual(store.get("k"), 1)
        # 用新事务重试即可成功。
        retry = store.begin()
        retry.put("k", retry.get("k") + 1)
        retry.commit()
        self.assertEqual(store.get("k"), 2)

    def test_delete_in_txn_and_snapshot(self):
        store = Store()
        store.put("k", "v")
        txn = store.begin()
        self.assertTrue(txn.delete("k"))
        self.assertFalse(txn.delete("missing"))
        self.assertIsNone(txn.get("k"))
        txn.commit()
        self.assertIsNone(store.get("k"))

    def test_version_advances_per_commit(self):
        store = Store()
        self.assertEqual(store._next_version, 0)
        store.put("a", 1)
        self.assertEqual(store._next_version, 1)
        store.delete("a")
        self.assertEqual(store._next_version, 2)
        t = store.begin()
        t.put("b", 1)
        t.put("c", 2)
        t.commit()
        # 一次事务提交只推进一个版本，写集内所有 key 共享该版本。
        self.assertEqual(store._next_version, 3)
        self.assertEqual(store._last_committed["b"], 2)
        self.assertEqual(store._last_committed["c"], 2)

    def test_context_manager_rollback_on_exception(self):
        store = Store()
        store.put("k", 0)
        with self.assertRaises(ValueError):
            with store.begin() as txn:
                txn.put("k", 1)
                raise ValueError("boom")
        self.assertEqual(store.get("k"), 0)
        with store.begin() as txn:
            txn.put("k", 2)
        self.assertEqual(store.get("k"), 2)

    def test_committed_txn_writes_are_journaled(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "store.log")
            store = Store(path)
            t = store.begin()
            t.put("a", {"n": 1})
            t.put("b", "中文")
            t.commit()
            t2 = store.begin()
            t2.delete("b")
            t2.commit()
            with open(path, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            self.assertEqual([r["op"] for r in records], ["put", "put", "del"])

            reopened = Store(path)
            self.assertEqual(reopened.get("a"), {"n": 1})
            self.assertIsNone(reopened.get("b"))


if __name__ == "__main__":
    unittest.main()
