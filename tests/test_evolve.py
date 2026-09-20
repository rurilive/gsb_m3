"""schema 演进：兼容判定、升降级读、注册表落盘恢复、性能。"""

import json
import os
import random
import tempfile
import time
import unittest

from evschema.compat import check_compatibility
from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema, SchemaError
from evschema.store import EventStore

TYPE_NAMES = ("str", "int", "float", "bool", "list", "dict")
FIELD_POOL = ("a", "b", "c", "d", "e", "f")


def order_v2():
    """v1 之上 note 改名 remark，新增带默认值的 channel。"""
    return Schema(
        "order",
        2,
        {"order_id": "str", "amount": "int", "remark": "str", "channel": "str"},
        required=("order_id", "amount"),
        defaults={"remark": "", "channel": "web"},
        renames={"note": "remark"},
    )


def order_v3():
    """v2 之上 remark 再改名 comment，新增带默认值的 priority。"""
    return Schema(
        "order",
        3,
        {
            "order_id": "str",
            "amount": "int",
            "comment": "str",
            "channel": "str",
            "priority": "int",
        },
        required=("order_id", "amount"),
        defaults={"comment": "", "channel": "web", "priority": 0},
        renames={"remark": "comment"},
    )


def sample_value(rng, type_name):
    return {
        "str": "x",
        "int": 1,
        "float": 1.5,
        "bool": True,
        "list": [],
        "dict": {},
    }[type_name]


def random_schema(rng, name, version):
    fields = {}
    for field in FIELD_POOL:
        if rng.random() < 0.6:
            fields[field] = rng.choice(TYPE_NAMES)
    if not fields:
        fields["a"] = "str"
    required = tuple(f for f in fields if rng.random() < 0.4)
    defaults = {}
    for field in fields:
        if field not in required and rng.random() < 0.4:
            defaults[field] = sample_value(rng, fields[field])
    renames = {}
    for field in FIELD_POOL:
        if rng.random() < 0.15:
            renames[field] = rng.choice(FIELD_POOL)
    return Schema(
        name, version, fields, required=required, defaults=defaults, renames=renames
    )


def naive_compatible(old, new):
    """朴素逐字段对拍实现：按任务口径独立直写，不做任何复用。"""
    if old.name != new.name:
        return False
    targets = set()
    for old_name, new_name in new.renames.items():
        if old_name not in old.fields:
            return False
        if new_name not in new.fields:
            return False
        if new_name in targets:
            return False
        targets.add(new_name)
        if new_name in old.fields and new_name != old_name:
            return False
    carried = set()
    for field, type_name in old.fields.items():
        mapped = new.renames.get(field, field)
        carried.add(mapped)
        if mapped not in new.fields:
            return False
        if new.fields[mapped] != type_name:
            return False
        if field not in old.required and mapped in new.required:
            return False
    for field in new.fields:
        if field not in carried and field not in new.defaults:
            return False
    return True


class TestCheckCompatibility(unittest.TestCase):
    def test_added_field_with_default_is_compatible(self):
        verdict = check_compatibility(ORDER_V1, order_v2())
        self.assertTrue(verdict.ok)
        self.assertEqual(verdict.reasons, ())

    def test_removed_field_rejected(self):
        new = Schema("order", 2, {"order_id": "str"}, required=("order_id",))
        verdict = check_compatibility(ORDER_V1, new)
        self.assertFalse(verdict.ok)
        self.assertIn("field removed: amount", verdict.reasons)

    def test_type_change_rejected(self):
        new = Schema(
            "order",
            2,
            {"order_id": "str", "amount": "str", "note": "str"},
            required=("order_id", "amount"),
            defaults={"note": ""},
        )
        verdict = check_compatibility(ORDER_V1, new)
        self.assertFalse(verdict.ok)
        self.assertIn("field amount type changed: int -> str", verdict.reasons)

    def test_optional_becoming_required_rejected(self):
        new = Schema(
            "order",
            2,
            {"order_id": "str", "amount": "int", "note": "str"},
            required=("order_id", "amount", "note"),
            defaults={"note": ""},
        )
        verdict = check_compatibility(ORDER_V1, new)
        self.assertFalse(verdict.ok)
        self.assertIn("optional field became required: note", verdict.reasons)

    def test_new_field_without_default_rejected(self):
        new = Schema(
            "order",
            2,
            {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
            required=("order_id", "amount"),
            defaults={"note": ""},
        )
        verdict = check_compatibility(ORDER_V1, new)
        self.assertFalse(verdict.ok)
        self.assertIn("new field without default: channel", verdict.reasons)

    def test_rename_counts_as_same_field(self):
        renamed = Schema(
            "order",
            2,
            {"order_id": "str", "amount": "int", "remark": "str"},
            required=("order_id", "amount"),
            defaults={"remark": ""},
            renames={"note": "remark"},
        )
        self.assertTrue(check_compatibility(ORDER_V1, renamed).ok)
        undeclared = Schema(
            "order",
            2,
            {"order_id": "str", "amount": "int", "remark": "str"},
            required=("order_id", "amount"),
            defaults={"remark": ""},
        )
        self.assertFalse(check_compatibility(ORDER_V1, undeclared).ok)

    def test_random_pairs_match_naive_implementation(self):
        rng = random.Random(20260921)
        for _ in range(2000):
            old = random_schema(rng, "thing", 1)
            new = random_schema(rng, "thing", 2)
            verdict = check_compatibility(old, new)
            self.assertEqual(
                verdict.ok,
                naive_compatible(old, new),
                "old=%r new=%r reasons=%r" % (old, new, verdict.reasons),
            )
            self.assertEqual(bool(verdict.reasons), not verdict.ok)


class EvolveStoreTestCase(unittest.TestCase):
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

    def fill_v1(self):
        self.store.append("order", {"order_id": "o-1", "amount": 10, "note": "gift"})
        self.store.append("order", {"order_id": "o-2", "amount": 20})


class TestRegisterCompatibility(EvolveStoreTestCase):
    def test_incompatible_version_rejected_at_register(self):
        bad = Schema("order", 2, {"order_id": "str"}, required=("order_id",))
        with self.assertRaises(SchemaError):
            self.registry.register(bad)
        self.assertEqual(self.registry.versions("order"), [1])

    def test_register_error_message_lists_reasons(self):
        bad = Schema("order", 2, {"order_id": "str"}, required=("order_id",))
        with self.assertRaises(SchemaError) as ctx:
            self.registry.register(bad)
        self.assertIn("field removed: amount", str(ctx.exception))


class TestRegistryPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "registry.json")

    def test_versions_and_verdicts_survive_restart(self):
        first = SchemaRegistry(self.path)
        first.register(ORDER_V1)
        first.register(order_v2())
        first.register(order_v3())
        before = check_compatibility(first.get("order", 1), first.get("order", 2))

        reopened = SchemaRegistry(self.path)
        self.assertEqual(reopened.versions("order"), [1, 2, 3])
        self.assertEqual(reopened.names(), ["order"])
        self.assertEqual(len(reopened), 3)
        self.assertEqual(reopened.get("order", 2).fields, order_v2().fields)
        self.assertEqual(reopened.get("order", 3).renames, {"remark": "comment"})
        after = check_compatibility(reopened.get("order", 1), reopened.get("order", 2))
        self.assertEqual(before, after)

    def test_rejected_registration_is_not_persisted(self):
        registry = SchemaRegistry(self.path)
        registry.register(ORDER_V1)
        with self.assertRaises(SchemaError):
            registry.register(
                Schema("order", 2, {"order_id": "str"}, required=("order_id",))
            )
        reopened = SchemaRegistry(self.path)
        self.assertEqual(reopened.versions("order"), [1])

    def test_reopened_registry_still_enforces_compatibility(self):
        SchemaRegistry(self.path).register(ORDER_V1)
        reopened = SchemaRegistry(self.path)
        with self.assertRaises(SchemaError):
            reopened.register(
                Schema("order", 2, {"order_id": "str"}, required=("order_id",))
            )
        reopened.register(order_v2())
        self.assertEqual(reopened.versions("order"), [1, 2])


class TestUpgradeRead(EvolveStoreTestCase):
    def test_old_events_upgraded_to_latest_with_renames_and_defaults(self):
        self.fill_v1()
        self.registry.register(order_v2())
        self.registry.register(order_v3())
        self.store.append(
            "order",
            {
                "order_id": "o-3",
                "amount": 30,
                "comment": "fresh",
                "channel": "app",
                "priority": 5,
            },
        )
        events = self.store.read()
        self.assertEqual([e["v"] for e in events], [3, 3, 3])
        self.assertEqual(
            events[0]["data"],
            {
                "order_id": "o-1",
                "amount": 10,
                "comment": "gift",
                "channel": "web",
                "priority": 0,
            },
        )
        self.assertEqual(events[1]["data"]["comment"], "")
        self.assertEqual(
            events[2]["data"],
            {
                "order_id": "o-3",
                "amount": 30,
                "comment": "fresh",
                "channel": "app",
                "priority": 5,
            },
        )

    def test_read_does_not_touch_the_file(self):
        self.fill_v1()
        self.registry.register(order_v2())
        self.registry.register(order_v3())
        before = self.read_bytes()
        self.store.read()
        self.store.read(version=1)
        self.assertEqual(self.read_bytes(), before)

    def test_downgrade_read_drops_undeclared_fields(self):
        self.fill_v1()
        self.registry.register(order_v2())
        self.registry.register(order_v3())
        events = self.store.read(version=1)
        self.assertEqual([e["v"] for e in events], [1, 1])
        self.assertEqual(
            events[0]["data"], {"order_id": "o-1", "amount": 10, "note": "gift"}
        )
        self.assertEqual(events[1]["data"], {"order_id": "o-2", "amount": 20})

    def test_downgrade_read_to_intermediate_version(self):
        self.fill_v1()
        self.registry.register(order_v2())
        self.registry.register(order_v3())
        events = self.store.read(version=2)
        self.assertEqual([e["v"] for e in events], [2, 2])
        self.assertEqual(
            events[0]["data"],
            {"order_id": "o-1", "amount": 10, "remark": "gift", "channel": "web"},
        )

    def test_stats_expose_upgrades_and_plan_builds(self):
        self.fill_v1()
        self.registry.register(order_v2())
        self.registry.register(order_v3())
        self.store.read()
        stats = self.store.stats()
        self.assertEqual(stats["upgrades"], 2)
        self.assertEqual(stats["plans"], 1)
        self.store.read()
        self.assertEqual(self.store.stats()["plans"], 1)
        self.assertEqual(self.store.stats()["upgrades"], 4)


class TestUpgradePerformance(unittest.TestCase):
    def test_100k_events_upgrade_read_under_10_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            total = 100000
            with open(path, "w", encoding="utf-8") as fh:
                for i in range(total):
                    fh.write(
                        json.dumps(
                            {
                                "seq": i + 1,
                                "type": "order",
                                "v": 1,
                                "data": {
                                    "order_id": "o-%d" % i,
                                    "amount": i,
                                    "note": "n",
                                },
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
            registry = SchemaRegistry()
            registry.register(ORDER_V1)
            registry.register(order_v2())
            registry.register(order_v3())
            store = EventStore(path, registry)
            started = time.monotonic()
            events = store.read()
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 10)
            self.assertEqual(len(events), total)
            self.assertEqual(events[0]["v"], 3)
            self.assertEqual(events[0]["data"]["comment"], "n")
            stats = store.stats()
            self.assertEqual(stats["upgrades"], total)
            self.assertEqual(stats["plans"], 1)


if __name__ == "__main__":
    unittest.main()
