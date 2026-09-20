"""十万条历史事件升级读的性能锁定：10 秒内，方案只建一次。"""

import os
import tempfile
import time
import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema
from evschema.store import EventStore


SCALE = 100_000


class UpgradeScaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = SchemaRegistry()
        self.registry.register(ORDER_V1)
        self.registry.register(
            Schema(
                "order", 2,
                {"order_id": "str", "amount": "int", "note": "str",
                 "channel": "str"},
                required=("order_id", "amount"),
                defaults={"note": "", "channel": "unknown"},
            )
        )
        self.registry.register(
            Schema(
                "order", 3,
                {"order_id": "str", "total": "int", "note": "str",
                 "channel": "str", "segment": "str"},
                required=("order_id", "total"),
                defaults={"note": "", "channel": "unknown", "segment": "none"},
                renames={"amount": "total"},
            )
        )
        self.path = os.path.join(self.tmp.name, "events.jsonl")
        self.store = EventStore(self.path, self.registry)

    def _seed(self, count):
        for index in range(count):
            self.store.append(
                "order",
                {"order_id": "o-%d" % index, "amount": index},
                version=1,
            )

    def test_one_hundred_thousand_upgrades_under_ten_seconds(self):
        self._seed(SCALE)
        bytes_before = open(self.path, "rb").read()
        started = time.perf_counter()
        events = self.store.read()
        elapsed = time.perf_counter() - started
        self.assertEqual(len(events), SCALE)
        self.assertEqual(events[0]["v"], 3)
        self.assertEqual(
            events[0]["data"],
            {"order_id": "o-0", "total": 0, "note": "",
             "channel": "unknown", "segment": "none"},
        )
        self.assertEqual(
            events[-1]["data"]["order_id"], "o-%d" % (SCALE - 1)
        )
        self.assertEqual(events[-1]["data"]["total"], SCALE - 1)
        self.assertEqual(open(self.path, "rb").read(), bytes_before)
        stats = self.store.stats()
        self.assertEqual(stats["upgraded"], SCALE)
        self.assertEqual(stats["plans_built"], 2)
        self.assertLess(elapsed, 10.0, "upgrade read took %.2fs" % elapsed)

    def test_repeated_reads_reuse_plans(self):
        self._seed(1000)
        self.store.read()
        plans_after_first = self.store.stats()["plans_built"]
        self.store.read()
        self.store.read(version=1)
        stats = self.store.stats()
        self.assertEqual(stats["plans_built"], plans_after_first)
        self.assertEqual(plans_after_first, 2)


if __name__ == "__main__":
    unittest.main()
