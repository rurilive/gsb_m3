"""CachedStore 现有行为的锁定测试（都是单线程下的语义）。"""

import unittest

from revcache.backend import Backend, TransientError
from revcache.cache import ValueCache
from revcache.service import CachedStore


class CachedStoreTest(unittest.TestCase):

    def setUp(self):
        self.backend = Backend()
        self.store = CachedStore(self.backend, ValueCache(capacity=4))

    def test_read_through_loads_once_then_hits(self):
        self.store.write("k", 1)
        self.assertEqual(self.store.read("k"), 1)
        reads = self.backend.stats()["reads"]
        self.assertEqual(self.store.read("k"), 1)
        self.assertEqual(self.backend.stats()["reads"], reads)

    def test_write_invalidates_the_cached_copy(self):
        self.store.write("k", 1)
        self.assertEqual(self.store.read("k"), 1)
        self.store.write("k", 2)
        self.assertEqual(self.store.read("k"), 2)
        self.assertEqual(self.backend.get("k"), 2)

    def test_read_absent_key_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.store.read("nope")

    def test_write_after_a_missed_read_is_visible(self):
        with self.assertRaises(KeyError):
            self.store.read("k")
        self.store.write("k", 5)
        self.assertEqual(self.store.read("k"), 5)

    def test_delete_drops_the_key_everywhere(self):
        self.store.write("k", 1)
        self.assertEqual(self.store.read("k"), 1)
        self.assertTrue(self.store.delete("k"))
        with self.assertRaises(KeyError):
            self.store.read("k")
        self.assertFalse(self.store.delete("k"))

    def test_transient_failure_reaches_the_caller(self):
        self.store.write("k", 1)
        self.backend.inject_fault("k", count=1)
        with self.assertRaises(TransientError):
            self.store.read("k")

    def test_values_stay_correct_with_a_tiny_cache(self):
        store = CachedStore(self.backend, ValueCache(capacity=1))
        store.write("a", 1)
        store.write("b", 2)
        self.assertEqual(store.read("a"), 1)
        self.assertEqual(store.read("b"), 2)
        self.assertEqual(store.read("a"), 1)

    def test_counters_after_a_mixed_workload(self):
        self.store.write("k", 1)
        self.store.read("k")
        self.store.read("k")
        self.store.write("k", 2)
        self.store.read("k")
        stats = self.store.stats()
        self.assertEqual(stats["reads"], 3)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 2)
        self.assertEqual(stats["loads"], 2)
        self.assertEqual(stats["writes"], 2)
        self.assertEqual(stats["deletes"], 0)


if __name__ == "__main__":
    unittest.main()
