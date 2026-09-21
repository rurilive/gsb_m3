"""SecondaryIndex 行为基线，锁定查询结果的既有语义。"""

import tempfile
import unittest

from kvsec.index import SecondaryIndex
from kvsec.store import KVStore


class SecondaryIndexTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = KVStore(self._tmp.name)
        self.index = SecondaryIndex(self.store, "status")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_lookup_sees_latest_write_without_manual_rebuild(self):
        self.store.put("o-1", {"status": "new", "amount": 10})
        self.store.put("o-2", {"status": "new", "amount": 20})
        self.assertEqual(self.index.lookup("new"), ["o-1", "o-2"])
        self.store.put("o-2", {"status": "paid", "amount": 20})
        self.assertEqual(self.index.lookup("new"), ["o-1"])
        self.assertEqual(self.index.lookup("paid"), ["o-2"])

    def test_delete_drops_only_that_key(self):
        for key in ("o-1", "o-2", "o-3"):
            self.store.put(key, {"status": "new"})
        self.store.delete("o-2")
        self.assertEqual(self.index.lookup("new"), ["o-1", "o-3"])
        self.store.delete("o-1")
        self.store.delete("o-3")
        self.assertEqual(self.index.lookup("new"), [])

    def test_missing_value_returns_empty_list(self):
        self.store.put("o-1", {"status": "new"})
        self.assertEqual(self.index.lookup("cancelled"), [])

    def test_non_string_or_missing_field_stays_out(self):
        self.store.put("o-1", {"status": "new"})
        self.store.put("o-2", {"note": "no status here"})
        self.store.put("o-3", {"status": 3})
        self.assertEqual(self.index.lookup("new"), ["o-1"])
        self.assertEqual(self.index.values(), ["new"])
        self.assertEqual(self.index.stats()["entries"], 1)

    def test_field_turns_non_string_leaves_index(self):
        self.store.put("o-1", {"status": "new"})
        self.store.put("o-2", {"status": "new"})
        self.store.put("o-1", {"status": None})
        self.store.put("o-2", {"amount": 5})
        self.assertEqual(self.index.lookup("new"), [])
        self.assertEqual(self.index.values(), [])
        self.assertEqual(self.index.stats()["entries"], 0)

    def test_values_sorted(self):
        for key, status in (("o-1", "paid"), ("o-2", "new"), ("o-3", "paid")):
            self.store.put(key, {"status": status})
        self.assertEqual(self.index.values(), ["new", "paid"])

    def test_many_keys_in_one_bucket(self):
        keys = ["o-%03d" % i for i in range(60)]
        for key in keys:
            self.store.put(key, {"status": "new"})
        self.assertEqual(self.index.lookup("new"), keys)
        self.store.delete("o-007")
        self.assertEqual(
            self.index.lookup("new"), [key for key in keys if key != "o-007"]
        )

    def test_rebuild_returns_entry_count(self):
        self.store.put("o-1", {"status": "new"})
        self.store.put("o-2", {"status": "paid"})
        self.store.put("o-3", {"status": "paid"})
        self.assertEqual(self.index.rebuild(), 3)
        self.assertEqual(self.index.lookup("paid"), ["o-2", "o-3"])
        self.assertEqual(self.index.stats()["entries"], 3)

    def test_second_index_on_other_field(self):
        amount_index = SecondaryIndex(self.store, "amount")
        self.store.put("o-1", {"status": "new", "amount": "10"})
        self.store.put("o-2", {"status": "new", "amount": "10"})
        self.store.put("o-3", {"status": "new", "amount": "20"})
        self.assertEqual(amount_index.lookup("10"), ["o-1", "o-2"])
        self.assertEqual(self.index.lookup("new"), ["o-1", "o-2", "o-3"])

    def test_stats_shape(self):
        self.store.put("o-1", {"status": "new"})
        self.index.lookup("new")
        stats = self.index.stats()
        for name in ("rebuilds", "lookups", "records_scanned", "entries"):
            self.assertIsInstance(stats[name], int)
        self.assertGreaterEqual(stats["records_scanned"], 1)
        self.assertEqual(stats["entries"], 1)


if __name__ == "__main__":
    unittest.main()
