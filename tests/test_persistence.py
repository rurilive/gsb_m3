"""注册表落盘与同路径重建恢复测试。"""

import json
import os
import tempfile
import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema, SchemaError
from evschema.store import EventStore

from tests.test_evolution import V2, V3


class RegistryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reg_path = os.path.join(self.tmp.name, "registry.jsonl")
        self.event_path = os.path.join(self.tmp.name, "events.jsonl")

    def test_reopen_restores_versions_and_definitions(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        registry.register(V2)
        registry.register(V3)
        reopened = SchemaRegistry(self.reg_path)
        self.assertEqual(reopened.names(), ["order"])
        self.assertEqual(reopened.versions("order"), [1, 2, 3])
        for version in (1, 2, 3):
            original = registry.get("order", version)
            restored = reopened.get("order", version)
            self.assertEqual(restored.fields, original.fields)
            self.assertEqual(restored.required, original.required)
            self.assertEqual(restored.defaults, original.defaults)
            self.assertEqual(restored.renames, original.renames)

    def test_judgments_are_identical_after_reopen(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        registry.register(V2)
        registry.register(V3)
        reopened = SchemaRegistry(self.reg_path)
        for low, high in ((1, 2), (2, 3)):
            self.assertEqual(
                registry.check_compatibility(
                    registry.get("order", low), registry.get("order", high)
                ),
                reopened.check_compatibility(
                    reopened.get("order", low), reopened.get("order", high)
                ),
            )
        bad = Schema(
            "order", 4,
            {"order_id": "str"},
            required=("order_id",),
        )
        self.assertFalse(
            reopened.check_compatibility(reopened.get("order", 3), bad)[0]
        )
        with self.assertRaises(SchemaError):
            reopened.register(bad)

    def test_incompatible_register_nothing_persisted(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int"},
            required=("order_id", "amount"),
        )
        with self.assertRaises(SchemaError):
            registry.register(bad)
        with open(self.reg_path, encoding="utf-8") as fh:
            lines = [line for line in fh.read().splitlines() if line]
        self.assertEqual(len(lines), 1)
        reopened = SchemaRegistry(self.reg_path)
        self.assertEqual(reopened.versions("order"), [1])

    def test_persistence_file_is_jsonl_records(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        registry.register(V2)
        with open(self.reg_path, encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual([record["version"] for record in records], [1, 2])
        self.assertEqual(records[1]["renames"], {})
        self.assertEqual(records[1]["defaults"]["channel"], "unknown")

    def test_store_read_after_registry_reopen(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        registry.register(V2)
        registry.register(V3)
        store = EventStore(self.event_path, registry)
        store.append("order", {"order_id": "o-1", "amount": 7}, version=1)
        store.append(
            "order",
            {"order_id": "o-2", "total": 8, "note": "n", "channel": "web",
             "segment": "s"},
            version=3,
        )
        reopened_registry = SchemaRegistry(self.reg_path)
        reopened_store = EventStore(self.event_path, reopened_registry)
        latest = reopened_store.read()
        self.assertEqual([event["v"] for event in latest], [3, 3])
        self.assertEqual(
            latest[0]["data"],
            {"order_id": "o-1", "total": 7, "note": "", "channel": "unknown",
             "segment": "none"},
        )
        self.assertEqual(
            latest[1]["data"],
            {"order_id": "o-2", "total": 8, "note": "n", "channel": "web",
             "segment": "s"},
        )
        self.assertEqual(
            [event["data"] for event in reopened_store.read(version=1)],
            [
                {"order_id": "o-1", "amount": 7},
                {"order_id": "o-2", "amount": 8, "note": "n"},
            ],
        )

    def test_append_continues_sequence_after_reopen(self):
        registry = SchemaRegistry(self.reg_path)
        registry.register(ORDER_V1)
        registry.register(V2)
        store = EventStore(self.event_path, registry)
        store.append("order", {"order_id": "o-1", "amount": 1}, version=1)
        reopened_registry = SchemaRegistry(self.reg_path)
        reopened_store = EventStore(self.event_path, reopened_registry)
        self.assertEqual(
            reopened_store.append(
                "order",
                {"order_id": "o-2", "amount": 2, "channel": "shop"},
                version=2,
            ),
            2,
        )
        self.assertEqual(reopened_store.count(), 2)


if __name__ == "__main__":
    unittest.main()
