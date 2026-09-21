"""EventStore 现有行为的锁定测试。"""

import json
import os
import tempfile
import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, SchemaError
from evschema.store import EventStore


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "events.jsonl")
        self.registry = SchemaRegistry()
        self.registry.register(ORDER_V1)
        self.store = EventStore(self.path, self.registry)

    def read_bytes(self):
        with open(self.path, "rb") as fh:
            return fh.read()


class TestAppendAndRead(StoreTestCase):
    def test_append_returns_sequence_numbers(self):
        self.assertEqual(self.store.append("order", {"order_id": "o-1", "amount": 10}), 1)
        self.assertEqual(self.store.append("order", {"order_id": "o-2", "amount": 20}), 2)

    def test_read_returns_events_in_write_order(self):
        self.store.append("order", {"order_id": "o-1", "amount": 10})
        self.store.append("order", {"order_id": "o-2", "amount": 20, "note": "gift"})
        events = self.store.read()
        self.assertEqual([e["seq"] for e in events], [1, 2])
        self.assertEqual([e["type"] for e in events], ["order", "order"])
        self.assertEqual([e["v"] for e in events], [1, 1])
        self.assertEqual(events[0]["data"], {"order_id": "o-1", "amount": 10})
        self.assertEqual(
            events[1]["data"], {"order_id": "o-2", "amount": 20, "note": "gift"}
        )

    def test_omitted_optional_field_stays_omitted(self):
        self.store.append("order", {"order_id": "o-1", "amount": 10})
        self.assertEqual(set(self.store.read()[0]["data"]), {"order_id", "amount"})

    def test_explicit_version_is_used(self):
        self.assertEqual(self.store.append("order", {"order_id": "o-1", "amount": 1}, 1), 1)
        self.assertEqual(self.store.read()[0]["v"], 1)

    def test_read_returns_fresh_copies(self):
        self.store.append("order", {"order_id": "o-1", "amount": 10})
        first = self.store.read()
        first[0]["data"]["amount"] = 999
        first[0]["seq"] = 42
        second = self.store.read()
        self.assertEqual(second[0]["data"], {"order_id": "o-1", "amount": 10})
        self.assertEqual(second[0]["seq"], 1)

    def test_read_missing_file_is_empty(self):
        self.assertEqual(EventStore(self.path, self.registry).read(), [])


class TestValidation(StoreTestCase):
    def test_invalid_data_rejected_and_nothing_written(self):
        self.store.append("order", {"order_id": "o-1", "amount": 10})
        before = self.read_bytes()
        with self.assertRaises(SchemaError):
            self.store.append("order", {"order_id": "o-2", "amount": "many"})
        self.assertEqual(self.read_bytes(), before)
        self.assertEqual(self.store.count(), 1)

    def test_unknown_type_rejected(self):
        with self.assertRaises(SchemaError):
            self.store.append("payment", {"payment_id": "p-1"})
        self.assertFalse(os.path.exists(self.path))

    def test_unknown_version_rejected(self):
        with self.assertRaises(SchemaError):
            self.store.append("order", {"order_id": "o-1", "amount": 1}, 5)


class TestCountAndStats(StoreTestCase):
    def test_count_tracks_appends(self):
        self.assertEqual(self.store.count(), 0)
        self.store.append("order", {"order_id": "o-1", "amount": 1})
        self.assertEqual(self.store.count(), 1)

    def test_stats_snapshot(self):
        self.store.append("order", {"order_id": "o-1", "amount": 1})
        self.store.read()
        self.store.read()
        stats = self.store.stats()
        self.assertEqual(stats["events"], 1)
        self.assertEqual(stats["appends"], 1)
        self.assertEqual(stats["reads"], 2)


class TestFileLayoutAndReopen(StoreTestCase):
    def test_file_is_one_json_object_per_line(self):
        self.store.append("order", {"order_id": "o-1", "amount": 7})
        with open(self.path, encoding="utf-8") as fh:
            lines = [line for line in fh.read().splitlines() if line]
        self.assertEqual(len(lines), 1)
        raw = json.loads(lines[0])
        self.assertEqual(raw["seq"], 1)
        self.assertEqual(raw["type"], "order")
        self.assertEqual(raw["v"], 1)
        self.assertEqual(raw["data"], {"order_id": "o-1", "amount": 7})

    def test_reopen_continues_sequence_and_sees_history(self):
        self.store.append("order", {"order_id": "o-1", "amount": 1})
        self.store.append("order", {"order_id": "o-2", "amount": 2})
        reopened = EventStore(self.path, self.registry)
        self.assertEqual(reopened.count(), 2)
        self.assertEqual(reopened.append("order", {"order_id": "o-3", "amount": 3}), 3)
        self.assertEqual([e["seq"] for e in reopened.read()], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
