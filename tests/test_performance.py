"""十万条历史事件升级读一遍的性能锁定。"""

import os
import tempfile
import time
import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, ORDER_V2, ORDER_V3
from evschema.store import EventStore

N = 100_000
LIMIT_SECONDS = 10.0


class TestHundredThousandUpgrade(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "events.jsonl")
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(ORDER_V2)
        registry.register(ORDER_V3)
        self.registry = registry
        self.store = EventStore(self.path, registry)

    def seed_v1_events(self):
        append = self.store.append
        for index in range(N):
            append(
                "order",
                {"order_id": "o-%d" % index, "amount": index},
                version=1,
            )

    def test_full_upgrade_read_under_ten_seconds(self):
        self.seed_v1_events()
        start = time.perf_counter()
        events = self.store.read()
        elapsed = time.perf_counter() - start
        self.assertEqual(len(events), N)
        self.assertEqual([events[0]["v"], events[-1]["v"]], [3, 3])
        self.assertEqual(events[0]["data"]["total_cents"], 0)
        self.assertEqual(events[-1]["data"]["total_cents"], N - 1)
        self.assertEqual(events[0]["data"]["channel"], "unknown")
        self.assertEqual(events[0]["data"]["priority"], "normal")
        self.assertNotIn("amount", events[0]["data"])
        stats = self.store.stats()
        self.assertEqual(stats["upgraded"], N)
        self.assertEqual(stats["plans_built"], 2)
        self.assertLess(
            elapsed,
            LIMIT_SECONDS,
            "升级读耗时 %.2fs 超过 %.0fs" % (elapsed, LIMIT_SECONDS),
        )

    def test_reread_reuses_two_plans(self):
        self.seed_v1_events()
        self.store.read()
        self.store.read()
        self.store.read(version=1)
        self.assertEqual(self.store.stats()["plans_built"], 2)


if __name__ == "__main__":
    unittest.main()
