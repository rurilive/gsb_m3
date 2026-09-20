"""schema 演进新行为：判定规则、随机对拍、读路径升降级与计数。"""

import copy
import os
import random
import tempfile
import unittest

from evschema.evolution import EdgePlan, check_compatibility
from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema, SchemaError
from evschema.store import EventStore


V2 = Schema(
    "order",
    2,
    {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
    required=("order_id", "amount"),
    defaults={"note": "", "channel": "unknown"},
)

V3 = Schema(
    "order",
    3,
    {
        "order_id": "str",
        "total": "int",
        "note": "str",
        "channel": "str",
        "segment": "str",
    },
    required=("order_id", "total"),
    defaults={"note": "", "channel": "unknown", "segment": "none"},
    renames={"amount": "total"},
)


class CheckCompatibilityRules(unittest.TestCase):
    def test_add_field_with_default_is_ok(self):
        ok, reason = check_compatibility(ORDER_V1, V2)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "")

    def test_rename_chain_is_ok(self):
        ok, reason = check_compatibility(V2, V3)
        self.assertTrue(ok, reason)

    def test_field_removal_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int"},
            required=("order_id", "amount"),
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("removed", reason)

    def test_type_change_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "str", "note": "str"},
            required=("order_id",),
            defaults={"note": ""},
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("type", reason)

    def test_optional_tightened_to_required_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str"},
            required=("order_id", "amount", "note"),
            defaults={"note": ""},
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("required", reason)

    def test_new_field_without_default_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
            required=("order_id", "amount"),
            defaults={"note": ""},
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("default", reason)

    def test_rename_unknown_source_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str"},
            required=("order_id", "amount"),
            defaults={"note": ""},
            renames={"ghost": "zzz"},
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("missing in old schema", reason)

    def test_rename_missing_target_rejected(self):
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str"},
            required=("order_id", "amount"),
            defaults={"note": ""},
            renames={"amount": "ghost"},
        )
        ok, reason = check_compatibility(ORDER_V1, bad)
        self.assertFalse(ok)
        self.assertIn("target", reason)

    def test_rename_type_mismatch_rejected(self):
        bad = Schema(
            "order", 3,
            {
                "order_id": "str",
                "total": "str",
                "note": "str",
                "channel": "str",
            },
            required=("order_id", "total"),
            defaults={"note": "", "channel": "unknown"},
            renames={"amount": "total"},
        )
        ok, reason = check_compatibility(V2, bad)
        self.assertFalse(ok)
        self.assertIn("type", reason)

    def test_rename_target_collision_rejected(self):
        old = Schema(
            "order", 1,
            {"a": "int", "x": "int", "y": "int"},
            required=("a", "x", "y"),
        )
        bad = Schema(
            "order", 2,
            {"a": "int", "b": "int"},
            required=("a",),
            defaults={"b": 0},
            renames={"x": "b", "y": "b"},
        )
        ok, reason = check_compatibility(old, bad)
        self.assertFalse(ok)
        self.assertIn("collide", reason)

    def test_rename_target_existing_field_rejected(self):
        old = Schema(
            "order", 1,
            {"a": "int", "x": "int"},
            required=("a", "x"),
        )
        bad = Schema(
            "order", 2,
            {"a": "int"},
            required=("a",),
            renames={"x": "a"},
        )
        ok, reason = check_compatibility(old, bad)
        self.assertFalse(ok)
        self.assertIn("already exists", reason)

    def test_lower_or_equal_version_rejected(self):
        self.assertFalse(check_compatibility(V2, ORDER_V1)[0])
        self.assertFalse(check_compatibility(V2, V2)[0])


class RegistryGateTests(unittest.TestCase):
    def test_incompatible_registration_raises_and_keeps_state(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        bad = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int"},
            required=("order_id", "amount"),
        )
        with self.assertRaises(SchemaError):
            registry.register(bad)
        self.assertEqual(registry.versions("order"), [1])

    def test_compatible_chain_registers(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(V2)
        registry.register(V3)
        self.assertEqual(registry.versions("order"), [1, 2, 3])


TYPES = ("str", "int", "float", "bool", "list", "dict")


def make_value(type_name, rng):
    if type_name == "str":
        return "v%d" % rng.randrange(1000)
    if type_name == "int":
        return rng.randrange(1000)
    if type_name == "float":
        return rng.random()
    if type_name == "bool":
        return rng.choice((True, False))
    if type_name == "list":
        return [rng.randrange(10)]
    return {"k": rng.randrange(10)}


def random_schema_pair(rng):
    """生成一对 (old, new)，字段数 1~5，Schema 构造本身合法。"""
    pool = ["f%d" % i for i in range(6)] + ["g%d" % i for i in range(6)]
    rng.shuffle(pool)
    old_names = pool[: rng.randint(1, 5)]
    old_fields = {name: rng.choice(TYPES) for name in old_names}
    old_required = [n for n in old_names if rng.random() < 0.7]
    old_defaults = {
        n: make_value(old_fields[n], rng)
        for n in old_names
        if n not in old_required and rng.random() < 0.5
    }
    old = Schema("evt", 1, old_fields, required=old_required, defaults=old_defaults)

    spare = [n for n in pool if n not in old_names]
    rng.shuffle(spare)
    spare_iter = iter(spare)

    new_fields = {}
    new_required = []
    new_defaults = {}
    renames = {}
    for name, type_name in old_fields.items():
        action = rng.choice(("keep", "rename", "drop"))
        if action == "drop":
            continue
        if action == "rename":
            target = next(spare_iter)
            new_type = type_name
            if rng.random() < 0.25:
                new_type = rng.choice([t for t in TYPES if t != new_type])
            new_fields[target] = new_type
            renames[name] = target
            if name in old_required:
                new_required.append(target)
            continue
        kept_type = type_name
        if rng.random() < 0.25:
            kept_type = rng.choice([t for t in TYPES if t != kept_type])
        new_fields[name] = kept_type
        if name in old_required:
            new_required.append(name)

    for _ in range(rng.randint(0, 3)):
        try:
            name = next(spare_iter)
        except StopIteration:
            break
        if name in new_fields:
            continue
        new_fields[name] = rng.choice(TYPES)

    for name, type_name in new_fields.items():
        if name in new_required:
            continue
        if rng.random() < 0.6:
            new_defaults[name] = make_value(type_name, rng)

    new = Schema(
        "evt", 2, new_fields,
        required=new_required, defaults=new_defaults, renames=renames,
    )
    return old, new


def naive_compatibility(old, new):
    """与 check_compatibility 同口径的朴素逐字段重写。"""
    if new.version <= old.version:
        return False
    targets = list(new.renames.values())
    if len(set(targets)) != len(targets):
        return False
    for source, target in new.renames.items():
        if source not in old.fields or target not in new.fields:
            return False
        if source == target:
            return False
        if old.fields[source] != new.fields[target]:
            return False
    for target in new.renames.values():
        if target in old.fields:
            return False
    for name in set(old.fields) - set(new.fields):
        if name not in new.renames:
            return False
    for name in set(old.fields) & set(new.fields):
        if name not in new.renames and old.fields[name] != new.fields[name]:
            return False
    for name in old.fields:
        if name in old.required:
            continue
        carried = new.renames.get(name, name)
        if carried in new.fields and carried in new.required:
            return False
    renamed = set(new.renames.values())
    for name in set(new.fields) - set(old.fields):
        if name not in renamed and name not in new.defaults:
            return False
    return True


class RandomCompatibilityOracleTests(unittest.TestCase):
    def test_random_pairs_match_naive_judge(self):
        rng = random.Random(20260921)
        compatible_seen = 0
        for _ in range(400):
            old, new = random_schema_pair(rng)
            expected = naive_compatibility(old, new)
            ok, reason = check_compatibility(old, new)
            self.assertIs(ok, expected, (old.fields, new.fields, new.renames, reason))
            if not expected:
                self.assertTrue(reason)
            compatible_seen += int(expected)
        self.assertGreater(compatible_seen, 20)


def random_data(schema, rng):
    data = {}
    for name in schema.field_names():
        type_name = schema.fields[name]
        if name in schema.required or rng.random() < 0.6:
            data[name] = make_value(type_name, rng)
    return data


def random_compatible_chain(rng):
    """生成一条保证相邻兼容的版本链（2~4 版），返回 Schema 列表。"""
    pool = ["f%d" % i for i in range(12)]
    rng.shuffle(pool)
    pool_iter = iter(pool)
    first = next(pool_iter)
    fields = {first: rng.choice(TYPES)}
    required = [first]
    defaults = {}
    versions = [Schema("evt", 1, fields, required=required, defaults=defaults)]
    for version in range(2, rng.randint(2, 4) + 1):
        new_fields = dict(fields)
        new_required = list(required)
        new_defaults = dict(defaults)
        renames = {}
        if fields and rng.random() < 0.5:
            source = rng.choice(list(fields))
            target = next(pool_iter)
            new_fields = {
                key: value
                for key, value in new_fields.items()
                if key != source
            }
            new_fields[target] = fields[source]
            new_required = [target if n == source else n for n in new_required]
            if source in new_defaults:
                new_defaults[target] = new_defaults.pop(source)
            renames[source] = target
        for _ in range(rng.randint(1, 2)):
            try:
                name = next(pool_iter)
            except StopIteration:
                break
            type_name = rng.choice(TYPES)
            new_fields[name] = type_name
            new_defaults[name] = make_value(type_name, rng)
        schema = Schema(
            "evt", version, new_fields,
            required=new_required, defaults=new_defaults, renames=renames,
        )
        ok, reason = check_compatibility(versions[-1], schema)
        assert ok, reason
        versions.append(schema)
        fields, required, defaults = new_fields, new_required, new_defaults
    return versions


def naive_step_upgrade(data, old, new):
    result = {}
    for target in new.field_names():
        source = None
        for src, tgt in new.renames.items():
            if tgt == target:
                source = src
                break
        if source is None and target in old.fields:
            source = target
        if source is not None and source in data:
            result[target] = copy.deepcopy(data[source])
        elif target in new.defaults:
            result[target] = copy.deepcopy(new.defaults[target])
    return result


def naive_step_downgrade(data, old, new):
    result = {}
    for name in old.field_names():
        new_name = new.renames.get(name, name)
        if new_name in data:
            result[name] = copy.deepcopy(data[new_name])
    return result


class RandomProjectionOracleTests(unittest.TestCase):
    def _build_store(self, versions):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = SchemaRegistry()
        for schema in versions:
            registry.register(schema)
        store = EventStore(os.path.join(tmp.name, "events.jsonl"), registry)
        return tmp, registry, store

    def test_projections_match_naive_step_by_step(self):
        rng = random.Random(9210021)
        for _ in range(40):
            versions = random_compatible_chain(rng)
            tmp, registry, store = self._build_store(versions)
            payloads = []
            for schema in versions:
                data = random_data(schema, rng)
                payloads.append((schema.version, data))
                store.append("evt", data, version=schema.version)

            latest = versions[-1]
            expected_latest = []
            for source_v, data in payloads:
                projected = copy.deepcopy(data)
                cursor = source_v
                while cursor < latest.version:
                    projected = naive_step_upgrade(
                        projected,
                        registry.get("evt", cursor),
                        registry.get("evt", cursor + 1),
                    )
                    cursor += 1
                expected_latest.append((latest.version, projected))
            got = store.read()
            self.assertEqual([e["v"] for e in got], [v for v, _ in expected_latest])
            for event, (version, data) in zip(got, expected_latest):
                self.assertEqual(event["v"], version)
                self.assertEqual(event["data"], data)

            for target_schema in versions:
                expected = []
                for source_v, data in payloads:
                    projected = copy.deepcopy(data)
                    cursor = source_v
                    if cursor < target_schema.version:
                        while cursor < target_schema.version:
                            projected = naive_step_upgrade(
                                projected,
                                                registry.get("evt", cursor),
                                registry.get("evt", cursor + 1),
                            )
                            cursor += 1
                    elif cursor > target_schema.version:
                        while cursor > target_schema.version:
                            projected = naive_step_downgrade(
                                projected,
                                registry.get("evt", cursor - 1),
                                registry.get("evt", cursor),
                            )
                            cursor -= 1
                    expected.append((target_schema.version, projected))
                got = store.read(version=target_schema.version)
                for event, (version, data) in zip(got, expected):
                    self.assertEqual(event["v"], version)
                    self.assertEqual(event["data"], data)

    def test_native_latest_event_returned_as_is_and_bytes_unchanged(self):
        versions = random_compatible_chain(random.Random(7))
        tmp, registry, store = self._build_store(versions)
        latest = versions[-1]
        data = random_data(latest, random.Random(8))
        store.append("evt", data, version=latest.version)
        before = open(store.path, "rb").read()
        got = store.read()[0]
        after = open(store.path, "rb").read()
        self.assertEqual(before, after)
        self.assertEqual(got["data"], data)
        self.assertEqual(got["v"], latest.version)

    def test_read_twice_gives_independent_copies(self):
        versions = random_compatible_chain(random.Random(9))
        tmp, registry, store = self._build_store(versions)
        store.append("evt", random_data(versions[0], random.Random(10)), version=1)
        first = store.read()
        first[0]["data"]["__mut__"] = 1
        second = store.read()
        self.assertNotIn("__mut__", second[0]["data"])

    def test_stats_count_upgrades_and_plans_built_once(self):
        versions = random_compatible_chain(random.Random(11))
        tmp, registry, store = self._build_store(versions)
        for _ in range(5):
            store.append("evt", random_data(versions[0], random.Random(12)), version=1)
        store.read()
        stats = store.stats()
        self.assertEqual(stats["upgraded"], 5)
        self.assertEqual(stats["plans_built"], len(versions) - 1)
        store.read()
        self.assertEqual(store.stats()["plans_built"], len(versions) - 1)
        self.assertEqual(store.stats()["upgraded"], 10)

    def test_downgrade_drops_new_fields_and_restores_renames(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(V2)
        registry.register(V3)
        store = EventStore(os.path.join(tmp.name, "events.jsonl"), registry)
        store.append(
            "order",
            {"order_id": "o-1", "total": 50, "note": "n", "channel": "web", "segment": "a"},
            version=3,
        )
        v2_event = store.read(version=2)[0]
        self.assertEqual(v2_event["v"], 2)
        self.assertEqual(
            v2_event["data"],
            {"order_id": "o-1", "amount": 50, "note": "n", "channel": "web"},
        )
        v1_event = store.read(version=1)[0]
        self.assertEqual(v1_event["v"], 1)
        self.assertEqual(v1_event["data"], {"order_id": "o-1", "amount": 50, "note": "n"})

    def test_read_unknown_target_version_raises(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        store = EventStore(os.path.join(tmp.name, "events.jsonl"), registry)
        store.append("order", {"order_id": "o-1", "amount": 1}, version=1)
        with self.assertRaises(SchemaError):
            store.read(version=2)

    def test_edge_plan_is_plain_operations(self):
        edge = EdgePlan(V2, V3)
        self.assertEqual((edge.name, edge.low, edge.high), ("order", 2, 3))
        upgraded = edge.upgrade({"order_id": "o", "amount": 9, "note": "n"})
        self.assertEqual(
            upgraded,
            {"order_id": "o", "total": 9, "note": "n", "channel": "unknown",
             "segment": "none"},
        )
        self.assertEqual(
            edge.downgrade(upgraded),
            {"order_id": "o", "amount": 9, "note": "n", "channel": "unknown"},
        )


if __name__ == "__main__":
    unittest.main()
