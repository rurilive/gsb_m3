"""read 升级/降级、注册表落盘重启恢复与读不改文件的锁定测试。"""

import json
import os
import tempfile
import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, ORDER_V2, ORDER_V3, Schema, SchemaError
from evschema.store import EventStore


V1_FIELDS = {"id": "str", "amount": "int", "note": "str"}


def payment_v1():
    return Schema("payment", 1, V1_FIELDS, required=("id", "amount"),
                  defaults={"note": ""})


def payment_v2():
    return Schema(
        "payment",
        2,
        {"id": "str", "amount": "int", "note": "str", "channel": "str"},
        required=("id", "amount"),
        defaults={"note": "", "channel": "unknown"},
    )


def payment_v3():
    return Schema(
        "payment",
        3,
        {
            "id": "str",
            "total_cents": "int",
            "note": "str",
            "channel": "str",
            "priority": "str",
        },
        required=("id", "total_cents"),
        defaults={"note": "", "channel": "unknown", "priority": "normal"},
        renames={"amount": "total_cents"},
    )


class EvolutionTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.events_path = os.path.join(self._tmp.name, "events.jsonl")
        self.registry_path = os.path.join(self._tmp.name, "registry.json")
        self.registry = SchemaRegistry()
        self.registry.register(payment_v1())
        self.registry.register(payment_v2())
        self.registry.register(payment_v3())
        self.store = EventStore(self.events_path, self.registry)

    def seed(self):
        self.store.append("payment", {"id": "p-1", "amount": 100}, version=1)
        self.store.append("payment", {"id": "p-2", "amount": 250, "note": "x"}, version=1)


class TestUpgradeRead(EvolutionTestCase):
    def test_default_read_upgrades_to_latest_and_bumps_v(self):
        self.seed()
        events = self.store.read()
        self.assertEqual([e["v"] for e in events], [3, 3])
        self.assertEqual(
            events[0]["data"],
            {
                "id": "p-1",
                "total_cents": 100,
                "channel": "unknown",
                "priority": "normal",
            },
        )
        self.assertEqual(
            events[1]["data"],
            {
                "id": "p-2",
                "total_cents": 250,
                "note": "x",
                "channel": "unknown",
                "priority": "normal",
            },
        )

    def test_rename_chain_followed_across_versions(self):
        self.seed()
        events = self.store.read()
        self.assertNotIn("amount", events[0]["data"])
        self.assertEqual(events[0]["data"]["total_cents"], 100)

    def test_already_latest_event_returned_as_is(self):
        self.store.append(
            "payment",
            {
                "id": "p-9",
                "total_cents": 5,
                "channel": "web",
                "priority": "high",
            },
            version=3,
        )
        events = self.store.read()
        self.assertEqual(events[0]["v"], 3)
        self.assertEqual(
            events[0]["data"],
            {"id": "p-9", "total_cents": 5, "channel": "web", "priority": "high"},
        )

    def test_read_twice_returns_independent_upgraded_copies(self):
        self.seed()
        first = self.store.read()
        first[0]["data"]["total_cents"] = 999
        second = self.store.read()
        self.assertEqual(second[0]["data"]["total_cents"], 100)

    def test_explicit_intermediate_version_upgrades_partway(self):
        self.seed()
        events = self.store.read(version=2)
        self.assertEqual([e["v"] for e in events], [2, 2])
        self.assertEqual(
            events[0]["data"],
            {"id": "p-1", "amount": 100, "channel": "unknown"},
        )

    def test_unknown_target_version_raises(self):
        self.seed()
        with self.assertRaises(SchemaError):
            self.store.read(version=9)


class TestDowngradeRead(EvolutionTestCase):
    def test_downgrade_to_v1_reverses_renames_and_drops_new_fields(self):
        self.seed()
        events = self.store.read(version=1)
        self.assertEqual([e["v"] for e in events], [1, 1])
        self.assertEqual(events[0]["data"], {"id": "p-1", "amount": 100})
        self.assertEqual(
            events[1]["data"], {"id": "p-2", "amount": 250, "note": "x"}
        )

    def test_downgrade_v3_event_drops_fields_added_after_target(self):
        self.store.append(
            "payment",
            {
                "id": "p-9",
                "total_cents": 7,
                "channel": "web",
                "priority": "high",
            },
            version=3,
        )
        v1 = self.store.read(version=1)[0]["data"]
        self.assertEqual(v1, {"id": "p-9", "amount": 7})
        v2 = self.store.read(version=2)[0]["data"]
        self.assertEqual(v2, {"id": "p-9", "amount": 7, "channel": "web"})


class TestFileNeverTouched(EvolutionTestCase):
    def test_upgrade_and_downgrade_reads_keep_bytes_identical(self):
        self.seed()
        before = self.read_bytes()
        self.store.read()
        mid = self.read_bytes()
        self.store.read(version=1)
        self.store.read(version=2)
        after = self.read_bytes()
        self.assertEqual(before, mid)
        self.assertEqual(before, after)

    def test_raw_file_still_carries_original_version(self):
        self.seed()
        self.store.read()
        self.store.read(version=1)
        with open(self.events_path, encoding="utf-8") as fh:
            raw = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual([event["v"] for event in raw], [1, 1])
        self.assertIn("amount", raw[0]["data"])

    def read_bytes(self):
        with open(self.events_path, "rb") as fh:
            return fh.read()


class TestStats(EvolutionTestCase):
    def test_stats_count_upgrades_and_plan_builds(self):
        self.seed()
        self.store.read()
        stats = self.store.stats()
        self.assertEqual(stats["upgraded"], 2)
        self.assertEqual(stats["plans_built"], 2)

    def test_plans_built_once_even_for_many_events_and_rereads(self):
        for i in range(50):
            self.store.append("payment", {"id": "p-%s" % i, "amount": i}, version=1)
        self.store.read()
        self.store.read()
        self.store.read(version=1)
        stats = self.store.stats()
        self.assertEqual(stats["upgraded"], 100)
        self.assertEqual(stats["plans_built"], 2)

    def test_latest_events_do_not_count_as_upgraded(self):
        self.store.append(
            "payment",
            {"id": "p-9", "total_cents": 1, "channel": "web", "priority": "high"},
            version=3,
        )
        self.store.read()
        self.assertEqual(self.store.stats()["upgraded"], 0)


class TestRegistryPersistenceAndRestart(EvolutionTestCase):
    def test_registry_file_round_trips_versions(self):
        persisted = SchemaRegistry(self.registry_path)
        persisted.register(payment_v1())
        persisted.register(payment_v2())
        self.assertTrue(os.path.exists(self.registry_path))
        reopened = SchemaRegistry(self.registry_path)
        self.assertEqual(reopened.versions("payment"), [1, 2])
        self.assertEqual(reopened.names(), ["payment"])
        self.assertEqual(
            reopened.get("payment", 2).fields, payment_v2().fields
        )
        self.assertEqual(
            reopened.get("payment", 2).defaults, payment_v2().defaults
        )
        self.assertEqual(
            reopened.get("payment", 2).renames, payment_v2().renames
        )
        self.assertEqual(
            reopened.get("payment", 2).required, payment_v2().required
        )

    def test_incompatible_registration_rejected_before_and_after_restart(self):
        persisted = SchemaRegistry(self.registry_path)
        persisted.register(payment_v1())
        bad = Schema(
            "payment",
            2,
            {"id": "str"},
            required=("id",),
        )
        with self.assertRaises(SchemaError):
            persisted.register(bad)
        reopened = SchemaRegistry(self.registry_path)
        self.assertEqual(reopened.versions("payment"), [1])
        with self.assertRaises(SchemaError):
            reopened.register(bad)

    def test_full_restart_upgrades_history_identically(self):
        self.seed()
        restarted_registry = SchemaRegistry(self.registry_path)
        restarted_registry.register(payment_v1())
        restarted_registry.register(payment_v2())
        restarted_registry.register(payment_v3())

        fresh_registry = SchemaRegistry(self.registry_path)
        self.assertEqual(fresh_registry.versions("payment"), [1, 2, 3])
        fresh_store = EventStore(self.events_path, fresh_registry)
        events = fresh_store.read()
        self.assertEqual([e["v"] for e in events], [3, 3])
        self.assertEqual(events[0]["data"]["total_cents"], 100)
        self.assertEqual(events[0]["data"]["priority"], "normal")

        v1_events = fresh_store.read(version=1)
        self.assertEqual(v1_events[1]["data"], {"id": "p-2", "amount": 250, "note": "x"})

    def test_in_memory_registry_writes_nothing(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(ORDER_V2)
        registry.register(ORDER_V3)
        self.assertEqual(registry.versions("order"), [1, 2, 3])
        self.assertFalse(any(fn.startswith(".registry-") for fn in os.listdir(self._tmp.name)))


if __name__ == "__main__":
    unittest.main()
