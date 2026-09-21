"""ConcurrentMap 单线程路径与接口契约的锁定测试。"""

import time
import unittest

from bucketmap.concurrent import ConcurrentMap
from bucketmap.reference import PlainMap

STATS_KEYS = {"puts", "gets", "deletes", "resizes", "migrated_buckets",
              "pending_buckets", "max_pause_ms", "tables_live", "entries", "size"}


def drive_migration(m, tick_key, timeout=2.0):
    """拿一个已有键做更新，带着进行中的迁移往前走，直到本轮扩容收尾。"""
    deadline = time.monotonic() + timeout
    tick = 0
    while True:
        st = m.stats()
        if st["pending_buckets"] == 0 and st["resizes"] > 0:
            return st
        if time.monotonic() >= deadline:
            return st
        tick += 1
        m.put(tick_key, tick)
        time.sleep(0.002)


class TestBasics(unittest.TestCase):
    def test_put_get_delete_and_items(self):
        m = ConcurrentMap(capacity=8)
        self.assertIsNone(m.put("a", 1))
        self.assertEqual(m.put("a", 2), 1)
        self.assertEqual(m.get("a"), 2)
        self.assertEqual(m.get("absent", "缺"), "缺")
        self.assertEqual(len(m), 1)
        self.assertEqual(sorted(m.items()), [("a", 2)])
        m.put("b", 2)
        m.put("c", 3)
        self.assertEqual(len(m), 3)
        self.assertTrue(m.delete("b"))
        self.assertEqual(sorted(m.items()), [("a", 2), ("c", 3)])
        self.assertTrue(m.delete("a"))
        self.assertFalse(m.delete("a"))
        self.assertIsNone(m.get("a"))
        self.assertEqual(len(m), 1)

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            ConcurrentMap(capacity=0)
        with self.assertRaises(ValueError):
            ConcurrentMap(load_factor=0)
        with self.assertRaises(ValueError):
            ConcurrentMap(batch=0)
        with self.assertRaises(ValueError):
            ConcurrentMap().put("a", None)

    def test_stats_shape_and_counters(self):
        m = ConcurrentMap(capacity=8)
        m.put("a", 1)
        m.get("a")
        m.get("absent")
        m.delete("a")
        st = m.stats()
        self.assertEqual(set(st), STATS_KEYS)
        self.assertEqual((st["puts"], st["gets"], st["deletes"]), (1, 2, 1))
        self.assertEqual(st["size"], 0)
        self.assertIsInstance(st["tables_live"], int)
        self.assertGreaterEqual(st["tables_live"], 1)

    def test_max_pause_ms_uses_injected_clock(self):
        ticks = [0.0]

        def clock():
            ticks[0] += 0.001
            return ticks[0]

        m = ConcurrentMap(capacity=8, clock=clock)
        for i in range(6):
            m.put("k%d" % i, i)
        pause = m.stats()["max_pause_ms"]
        self.assertGreater(pause, 0.0)
        self.assertLess(pause, 1000.0)


class TestResize(unittest.TestCase):
    def test_resize_moves_everything(self):
        m = ConcurrentMap(capacity=4, load_factor=0.75)
        for i in range(6):
            m.put("k%d" % i, i)
        st = drive_migration(m, "k0")
        self.assertEqual((st["pending_buckets"], st["resizes"]), (0, 1))
        self.assertEqual(st["migrated_buckets"], 4)
        self.assertEqual(st["entries"], st["size"])
        for i in range(6):
            m.put("k%d" % i, i)
        for i in range(6):
            self.assertEqual(m.get("k%d" % i), i)
        self.assertEqual(len(m), 6)

    def test_migration_advances_with_writes(self):
        m = ConcurrentMap(capacity=4, load_factor=0.75)
        for i in range(4):
            m.put("k%d" % i, i)                 # 这一写触发扩容并推进一批
        st = drive_migration(m, "k0")
        self.assertGreaterEqual(st["migrated_buckets"], 1)
        self.assertEqual(st["pending_buckets"], 0)

    def test_step_hook_contract(self):
        calls = []
        m = ConcurrentMap(capacity=4, load_factor=0.75, batch=1,
                          step_hook=lambda done, total: calls.append((done, total)))
        for i in range(4):
            m.put("k%d" % i, i)
        self.assertEqual(drive_migration(m, "k0")["pending_buckets"], 0)
        self.assertEqual(calls[-1], (4, 4))
        done = [d for d, _t in calls]
        self.assertEqual(done, sorted(done))
        self.assertEqual(len(set(done)), len(done))
        for d, total in calls:
            self.assertEqual(total, 4)
            self.assertLessEqual(d, total)

    def test_delete_and_update_across_a_resize(self):
        m = ConcurrentMap(capacity=4, load_factor=0.75)
        for i in range(3):
            m.put("k%d" % i, i)
        m.put("k3", 3)                 # 这一写触发扩容
        self.assertTrue(m.delete("k1"))
        self.assertEqual(drive_migration(m, "k2")["pending_buckets"], 0)
        self.assertIsNone(m.get("k1"))
        self.assertFalse(m.delete("k1"))
        m.put("k2", 22)
        for i in range(6):
            m.put("extra%d" % i, i)
        self.assertEqual(m.get("k2"), 22)
        self.assertEqual([k for k, _v in m.items()].count("k2"), 1)
        self.assertEqual(sorted(k for k, _v in m.items()),
                         sorted(["k0", "k2", "k3"] + ["extra%d" % i for i in range(6)]))
        st = m.stats()
        self.assertEqual((st["entries"], st["size"]), (len(m), len(m)))


class TestReference(unittest.TestCase):
    def test_plain_map_matches_hash_map_semantics(self):
        ref = PlainMap()
        self.assertIsNone(ref.put("a", 1))
        self.assertEqual(ref.put("a", 2), 1)
        self.assertTrue(ref.delete("a"))
        self.assertFalse(ref.delete("a"))
        self.assertEqual(len(ref), 0)
        self.assertNotIn("a", ref)


if __name__ == "__main__":
    unittest.main()
