"""Backend 现有行为的锁定测试。"""

import unittest

from revcache.backend import Backend, TransientError


class BackendTest(unittest.TestCase):

    def setUp(self):
        self.backend = Backend()

    def test_set_then_get(self):
        self.backend.set("k", 1)
        self.assertEqual(self.backend.get("k"), 1)
        self.backend.set("k", 2)
        self.assertEqual(self.backend.get("k"), 2)

    def test_get_absent_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.backend.get("nope")

    def test_snapshot_returns_value_with_its_revision(self):
        rev = self.backend.set("k", "v")
        self.assertEqual(self.backend.snapshot("k"), ("v", rev))

    def test_revision_grows_with_every_change(self):
        first = self.backend.set("k", 1)
        second = self.backend.set("k", 2)
        self.assertGreater(second, first)

    def test_revision_survives_delete(self):
        self.backend.set("k", 1)
        second = self.backend.set("k", 2)
        self.assertTrue(self.backend.delete("k"))
        third = self.backend.revision("k")
        self.assertGreater(third, second)
        self.assertEqual(self.backend.set("k", 3), third + 1)

    def test_delete_absent_key_returns_false(self):
        self.assertFalse(self.backend.delete("nope"))
        self.assertEqual(self.backend.revision("nope"), 0)

    def test_inject_fault_fails_once_then_recovers(self):
        self.backend.set("k", 1)
        self.backend.inject_fault("k", count=1)
        with self.assertRaises(TransientError):
            self.backend.get("k")
        self.assertEqual(self.backend.get("k"), 1)

    def test_injected_latency_uses_injected_sleep(self):
        slept = []
        backend = Backend(sleep=slept.append)
        backend.set("k", 1)
        backend.inject_latency(0.01)
        backend.get("k")
        self.assertEqual(slept, [0.01])
        backend.inject_latency(0.25, key="k")
        backend.get("k")
        self.assertEqual(slept, [0.01, 0.25])

    def test_stats_counts_reads_and_writes(self):
        self.backend.set("k", 1)
        self.backend.get("k")
        stats = self.backend.stats()
        self.assertEqual(stats["writes"], 1)
        self.assertEqual(stats["reads"], 1)


if __name__ == "__main__":
    unittest.main()
