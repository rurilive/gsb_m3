"""SnowflakeGenerator 行为测试：多实例唯一、顺序、时钟回拨、大促并发。"""
import tempfile
import threading
import time
import unittest

from idgen import (
    ClockMovedBackwardsError,
    DuplicateInstanceError,
    FileInstanceRegistry,
    SnowflakeGenerator,
)
from idgen.snowflake import EPOCH_MS, SEQUENCE_MASK

BASE_MS = 1700000001000


class FakeClock:
    def __init__(self, ms):
        self.ms = ms

    def __call__(self):
        return self.ms / 1000.0


def timestamp_part(snowflake_id):
    return snowflake_id >> 22


def instance_part(snowflake_id):
    return (snowflake_id >> 12) & 0x3FF


class TestBitLayout(unittest.TestCase):
    def test_layout_and_instance_range(self):
        g = SnowflakeGenerator(7, clock=FakeClock(BASE_MS))
        snowflake_id = g.next_id()
        self.assertEqual(timestamp_part(snowflake_id), BASE_MS - EPOCH_MS)
        self.assertEqual(instance_part(snowflake_id), 7)
        self.assertEqual(snowflake_id & 0xFFF, 0)
        with self.assertRaises(ValueError):
            SnowflakeGenerator(1024)
        with self.assertRaises(ValueError):
            SnowflakeGenerator(-1)


class TestMultiInstance(unittest.TestCase):
    def test_three_instances_no_duplicates_under_threads(self):
        clock = FakeClock(BASE_MS)
        generators = [SnowflakeGenerator(i, clock=clock) for i in range(3)]
        results = [[] for _ in generators]

        def worker(index, out):
            for _ in range(500):
                out.append(generators[index].next_id())

        threads = []
        for index in range(3):
            for _ in range(8):
                thread = threading.Thread(target=worker,
                                          args=(index, results[index]))
                thread.start()
                threads.append(thread)
        for thread in threads:
            thread.join()

        all_ids = [i for out in results for i in out]
        self.assertEqual(len(all_ids), 3 * 8 * 500)
        self.assertEqual(len(set(all_ids)), len(all_ids))
        self.assertEqual({instance_part(i) for i in all_ids}, {0, 1, 2})

    def test_ordering_by_time_across_instances(self):
        clock = FakeClock(BASE_MS)
        generators = [SnowflakeGenerator(i, clock=clock) for i in range(3)]
        emitted = []
        for step in range(50):
            clock.ms = BASE_MS + step
            for g in generators:
                emitted.append(g.next_id())
        emitted.sort()
        timestamps = [timestamp_part(i) for i in emitted]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_single_instance_strictly_increasing(self):
        clock = FakeClock(BASE_MS)
        g = SnowflakeGenerator(0, clock=clock)
        ids = [g.next_id() for _ in range(1000)]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), len(ids))


class TestClockRollback(unittest.TestCase):
    def test_small_rollback_stays_monotonic(self):
        clock = FakeClock(BASE_MS + 8000)
        g = SnowflakeGenerator(0, clock=clock)
        before = [g.next_id() for _ in range(100)]
        clock.ms -= 8000
        during = [g.next_id() for _ in range(100)]
        clock.ms += 8000
        after = [g.next_id() for _ in range(100)]
        all_ids = before + during + after
        self.assertEqual(all_ids, sorted(all_ids))
        self.assertEqual(len(set(all_ids)), len(all_ids))

    def test_large_rollback_raises(self):
        clock = FakeClock(BASE_MS + 60_000)
        g = SnowflakeGenerator(0, clock=clock, max_rollback_ms=5000)
        g.next_id()
        clock.ms -= 10_000
        with self.assertRaises(ClockMovedBackwardsError):
            g.next_id()


class TestSequenceOverflow(unittest.TestCase):
    def test_overflow_waits_for_next_ms_instead_of_wrapping(self):
        clock = FakeClock(BASE_MS)
        g = SnowflakeGenerator(0, clock=clock)

        def advance_clock():
            time.sleep(0.05)
            clock.ms += 1

        thread = threading.Thread(target=advance_clock)
        thread.start()
        ids = [g.next_id() for _ in range(SEQUENCE_MASK + 2)]
        thread.join()

        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids[-1] >> 22, BASE_MS + 1 - EPOCH_MS)
        self.assertEqual(ids[-1] & 0xFFF, 0)

    def test_throughput_stays_microsecond_level(self):
        g = SnowflakeGenerator(0)
        count = 20000
        start = time.perf_counter()
        for _ in range(count):
            g.next_id()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed / count, 50e-6)


class TestInstanceRegistry(unittest.TestCase):
    def test_duplicate_instance_id_detected_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = FileInstanceRegistry(directory)
            SnowflakeGenerator(3, registry=registry)
            with self.assertRaises(DuplicateInstanceError):
                SnowflakeGenerator(3, registry=registry)

    def test_release_frees_instance_id(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = FileInstanceRegistry(directory)
            g = SnowflakeGenerator(3, registry=registry)
            g.close()
            SnowflakeGenerator(3, registry=registry).close()

    def test_expired_lease_can_be_reclaimed(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = FakeClock(BASE_MS)
            registry = FileInstanceRegistry(directory, ttl_seconds=30,
                                            clock=clock)
            SnowflakeGenerator(3, registry=registry)
            clock.ms += 31_000
            SnowflakeGenerator(3, registry=registry).close()


if __name__ == "__main__":
    unittest.main()
