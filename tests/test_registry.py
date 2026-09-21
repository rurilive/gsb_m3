"""Registry 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from shardcount.counter import LockCounter
from shardcount.registry import Registry


class FakeCounter:
    """只记名字的最小计数器，用来验证工厂可注入。"""

    def __init__(self, name):
        self.name = name
        self.incrs = 0

    def incr(self, key, delta=1):
        self.incrs += delta
        return self.incrs


class RegistryTest(unittest.TestCase):
    def test_open_returns_same_instance_per_name(self):
        registry = Registry()
        self.assertIs(registry.open("hits"), registry.open("hits"))

    def test_different_names_get_different_counters(self):
        registry = Registry()
        self.assertIsNot(registry.open("hits"), registry.open("errors"))

    def test_default_counter_is_lock_counter(self):
        self.assertIsInstance(Registry().open("hits"), LockCounter)

    def test_factory_is_injectable(self):
        registry = Registry(factory=lambda name: FakeCounter(name))
        counter = registry.open("hits")
        self.assertIsInstance(counter, FakeCounter)
        self.assertEqual(counter.name, "hits")

    def test_bind_replaces_existing_counter(self):
        registry = Registry()
        original = registry.open("hits")
        replacement = LockCounter()
        registry.bind("hits", replacement)
        self.assertIs(registry.open("hits"), replacement)
        self.assertIsNot(registry.open("hits"), original)

    def test_get_unopened_name_raises(self):
        with self.assertRaises(KeyError):
            Registry().get("ghost")

    def test_names_sorted(self):
        registry = Registry()
        registry.open("b")
        registry.open("a")
        self.assertEqual(registry.names(), ["a", "b"])

    def test_drop_then_open_creates_fresh(self):
        registry = Registry()
        first = registry.open("hits")
        self.assertTrue(registry.drop("hits"))
        self.assertFalse(registry.drop("hits"))
        self.assertIsNot(registry.open("hits"), first)

    def test_concurrent_open_returns_one_instance(self):
        registry = Registry()
        seen = []
        barrier = threading.Barrier(8)

        def grab():
            barrier.wait()
            seen.append(registry.open("hits"))

        workers = [threading.Thread(target=grab) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(len(seen), 8)
        self.assertEqual(len({id(counter) for counter in seen}), 1)


if __name__ == "__main__":
    unittest.main()
