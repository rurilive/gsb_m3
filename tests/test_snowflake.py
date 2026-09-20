"""多实例 Snowflake 行为：唯一性、顺序、时钟回拨、大促并发。"""
import tempfile
import threading
import time
import unittest

from idgen import (
    ClockMovedBackwardsError,
    FileInstanceRegistry,
    IdGenerator,
    InstanceIdInUseError,
)
from idgen.gen import COUNTER_BITS, COUNTER_MASK, EPOCH_MS, TIMESTAMP_SHIFT

BASE_MS = 1700000001000


class FakeClock:
    def __init__(self, ms):
        self.ms = ms
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self.ms / 1000.0

    def set_ms(self, ms):
        with self._lock:
            self.ms = ms


def decode(i):
    return (i >> TIMESTAMP_SHIFT, (i >> COUNTER_BITS) & 0xF, i & COUNTER_MASK)


class TestMultiInstance(unittest.TestCase):
    def test_instances_never_collide(self):
        clock = FakeClock(BASE_MS)
        gens = [IdGenerator(clock, instance_id=i) for i in range(3)]
        ids = [g.next_id() for g in gens for _ in range(1000)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_instance_id_is_encoded(self):
        clock = FakeClock(BASE_MS)
        for i in range(3):
            _, inst, _ = decode(IdGenerator(clock, instance_id=i).next_id())
            self.assertEqual(inst, i)

    def test_ids_stay_ordered_by_time_across_instances(self):
        clock = FakeClock(BASE_MS)
        gens = [IdGenerator(clock, instance_id=i) for i in range(3)]
        ids = []
        for t in range(200):
            clock.set_ms(BASE_MS + t)
            for g in gens:
                ids.append(g.next_id())
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_invalid_instance_id_rejected(self):
        with self.assertRaises(ValueError):
            IdGenerator(instance_id=16)


class TestClockRollback(unittest.TestCase):
    def test_rollback_8s_no_duplicates_and_monotonic(self):
        clock = FakeClock(BASE_MS)
        g = IdGenerator(clock)
        before = [g.next_id() for _ in range(100)]
        clock.set_ms(BASE_MS - 8000)
        during = [g.next_id() for _ in range(100)]
        clock.set_ms(BASE_MS)
        after = [g.next_id() for _ in range(100)]
        all_ids = before + during + after
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(all_ids, sorted(all_ids))

    def test_rollback_with_exhausted_counter_raises(self):
        clock = FakeClock(BASE_MS)
        g = IdGenerator(clock, max_wait_ms=50)
        for _ in range(COUNTER_MASK + 1):
            g.next_id()
        clock.set_ms(BASE_MS - 8000)
        with self.assertRaises(ClockMovedBackwardsError):
            g.next_id()


class TestCounterOverflow(unittest.TestCase):
    def test_overflow_waits_for_next_ms_instead_of_wrapping(self):
        clock = FakeClock(BASE_MS)
        g = IdGenerator(clock)
        for _ in range(COUNTER_MASK + 1):
            g.next_id()
        result = []

        def worker():
            result.append(g.next_id())

        t = threading.Thread(target=worker)
        t.start()
        time.sleep(0.05)
        clock.set_ms(BASE_MS + 1)
        t.join(timeout=2)
        self.assertFalse(t.is_alive())
        ms, _, counter = decode(result[0])
        self.assertEqual(ms, BASE_MS + 1 - EPOCH_MS)
        self.assertEqual(counter, 0)


class TestBurstConcurrency(unittest.TestCase):
    def test_three_instances_many_threads_unique_and_fast(self):
        gens = [IdGenerator(instance_id=i) for i in range(3)]
        ids = []
        ids_lock = threading.Lock()

        def worker(g):
            local = [g.next_id() for _ in range(500)]
            with ids_lock:
                ids.extend(local)

        start = time.monotonic()
        threads = [threading.Thread(target=worker, args=(g,))
                   for g in gens for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start
        self.assertEqual(len(ids), len(set(ids)))
        self.assertLess(elapsed, 2.0)


class TestInstanceRegistry(unittest.TestCase):
    def test_duplicate_instance_id_detected_at_startup(self):
        with tempfile.TemporaryDirectory() as d:
            reg = FileInstanceRegistry(d)
            g1 = IdGenerator(instance_id=1, registry=reg, owner="host-a")
            with self.assertRaises(InstanceIdInUseError):
                IdGenerator(instance_id=1, registry=reg, owner="host-b")
            g2 = IdGenerator(instance_id=2, registry=reg, owner="host-b")
            self.assertNotEqual(g1.next_id(), g2.next_id())
            g1.close()
            g2.close()

    def test_stale_claim_can_be_taken_over(self):
        with tempfile.TemporaryDirectory() as d:
            clock = FakeClock(BASE_MS)
            reg = FileInstanceRegistry(d, stale_ms=1000, clock=clock)
            g1 = IdGenerator(instance_id=1, registry=reg, owner="host-a")
            g1._stop_heartbeat.set()  # 模拟实例宕机：占位文件遗留但心跳停止
            clock.set_ms(BASE_MS + 5000)
            g = IdGenerator(instance_id=1, registry=reg, owner="host-b")
            g.close()


if __name__ == "__main__":
    unittest.main()
