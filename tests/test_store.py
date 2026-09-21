"""KVStore 行为基线，锁定主数据读写、重放与通知的既有语义。"""

import os
import tempfile
import unittest

from kvsec.codec import encode_line
from kvsec.store import KVStore


class PutGetDeleteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_put_get_overwrite_delete(self):
        with KVStore(self.path) as store:
            self.assertIsNone(store.get("o-1"))
            store.put("o-1", {"status": "new", "amount": 10})
            self.assertEqual(store.get("o-1"), {"status": "new", "amount": 10})
            store.put("o-1", {"status": "paid", "amount": 10})
            self.assertEqual(store.get("o-1")["status"], "paid")
            self.assertTrue(store.delete("o-1"))
            self.assertIsNone(store.get("o-1"))
            self.assertFalse(store.delete("o-1"))

    def test_put_returns_sequence(self):
        with KVStore(self.path) as store:
            self.assertEqual(store.put("o-1", {"status": "new"}), 1)
            self.assertEqual(store.put("o-2", {"status": "new"}), 2)
            self.assertEqual(store.delete("o-1"), True)
            self.assertEqual(store.sequence(), 3)

    def test_get_returns_independent_copy(self):
        with KVStore(self.path) as store:
            store.put("o-1", {"status": "new"})
            record = store.get("o-1")
            record["status"] = "tampered"
            self.assertEqual(store.get("o-1"), {"status": "new"})

    def test_keys_and_scan_sorted(self):
        with KVStore(self.path) as store:
            for key in ("o-3", "o-1", "o-2"):
                store.put(key, {"status": "new"})
            store.delete("o-2")
            self.assertEqual(store.keys(), ["o-1", "o-3"])
            self.assertEqual(
                store.scan(),
                [("o-1", {"status": "new"}), ("o-3", {"status": "new"})],
            )

    def test_bad_key_rejected(self):
        with KVStore(self.path) as store:
            for bad in ("", "o 1", "o\n1", 7, None):
                with self.assertRaises(ValueError):
                    store.put(bad, {"status": "new"})
            with self.assertRaises(TypeError):
                store.put("o-1", ["not", "a", "dict"])

    def test_closed_store_refuses_work(self):
        store = KVStore(self.path)
        store.put("o-1", {"status": "new"})
        store.close()
        with self.assertRaises(ValueError):
            store.put("o-2", {"status": "new"})
        with self.assertRaises(ValueError):
            store.get("o-1")


class ReopenTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_reopen_keeps_latest_records(self):
        store = KVStore(self.path)
        store.put("o-1", {"status": "new"})
        store.put("o-2", {"status": "paid"})
        store.put("o-1", {"status": "cancelled"})
        store.delete("o-2")
        store.close()
        with KVStore(self.path) as reopened:
            self.assertEqual(reopened.keys(), ["o-1"])
            self.assertEqual(reopened.get("o-1"), {"status": "cancelled"})
            self.assertEqual(reopened.sequence(), 4)

    def test_torn_tail_record_is_dropped(self):
        store = KVStore(self.path)
        store.put("o-1", {"status": "new"})
        store.close()
        # 模拟写记录写到一半进程没了：文件末尾多出半截记录
        data_path = os.path.join(self.path, "data.log")
        with open(data_path, "ab") as fh:
            fh.write(encode_line(2, "P", "o-2", {"status": "paid"})[:-4])
        with KVStore(self.path) as reopened:
            self.assertEqual(reopened.keys(), ["o-1"])
            self.assertEqual(reopened.sequence(), 1)
            reopened.put("o-3", {"status": "new"})
            self.assertEqual(reopened.sequence(), 2)
            self.assertEqual(reopened.keys(), ["o-1", "o-3"])
        with KVStore(self.path) as again:
            self.assertEqual(again.keys(), ["o-1", "o-3"])

    def test_corrupt_line_stops_replay(self):
        store = KVStore(self.path)
        store.put("o-1", {"status": "new"})
        store.put("o-2", {"status": "paid"})
        store.close()
        data_path = os.path.join(self.path, "data.log")
        with open(data_path, "r+b") as fh:
            raw = fh.read()
            at = raw.index(b"o-2")
            fh.seek(at)
            fh.write(b"o-9")
        with KVStore(self.path) as reopened:
            self.assertEqual(reopened.keys(), ["o-1"])
            self.assertEqual(reopened.sequence(), 1)
        # 坏行连同它后面的一切都被截掉，文件回到干净状态
        with KVStore(self.path) as reopened:
            self.assertEqual(reopened.keys(), ["o-1"])
            self.assertEqual(reopened.sequence(), 1)


class SubscribeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_events_carry_old_and_new(self):
        events = []
        with KVStore(self.path) as store:
            store.subscribe(lambda key, old, new: events.append((key, old, new)))
            store.put("o-1", {"status": "new"})
            store.put("o-1", {"status": "paid"})
            store.delete("o-1")
            store.delete("o-1")
        self.assertEqual(
            events,
            [
                ("o-1", None, {"status": "new"}),
                ("o-1", {"status": "new"}, {"status": "paid"}),
                ("o-1", {"status": "paid"}, None),
            ],
        )

    def test_unsubscribe(self):
        seen = []

        def callback(key, old, new):
            seen.append(key)

        with KVStore(self.path) as store:
            store.subscribe(callback)
            store.put("o-1", {"status": "new"})
            self.assertTrue(store.unsubscribe(callback))
            store.put("o-2", {"status": "new"})
            self.assertFalse(store.unsubscribe(callback))
        self.assertEqual(seen, ["o-1"])

    def test_replayed_records_do_not_notify(self):
        store = KVStore(self.path)
        store.put("o-1", {"status": "new"})
        store.close()
        seen = []
        with KVStore(self.path) as reopened:
            reopened.subscribe(lambda key, old, new: seen.append(key))
            reopened.put("o-2", {"status": "new"})
        self.assertEqual(seen, ["o-2"])


class StatsTest(unittest.TestCase):
    def test_stats_shape(self):
        with tempfile.TemporaryDirectory() as path:
            with KVStore(path) as store:
                store.put("o-1", {"status": "new"})
                store.put("o-2", {"status": "new"})
                store.delete("o-1")
                store.get("o-2")
                store.scan()
                stats = store.stats()
                for name in ("keys", "puts", "deletes", "gets", "scans", "sequence"):
                    self.assertIsInstance(stats[name], int)
                self.assertEqual(stats["keys"], 1)
                self.assertEqual(stats["puts"], 2)
                self.assertEqual(stats["deletes"], 1)
                self.assertEqual(stats["sequence"], 3)
                self.assertGreaterEqual(stats["scans"], 1)


if __name__ == "__main__":
    unittest.main()
