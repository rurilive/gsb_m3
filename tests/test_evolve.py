"""check_compatibility 与 StepPlan 的行为测试。

随机生成新旧 schema 对，用一份朴素逐字段参考实现与 evolve.check_compatibility
对拍（判定 bool 与理由列表都要一致）。参考实现独立于生产代码重写规则。
"""

import random
import unittest

from evschema.evolve import StepPlan, check_compatibility
from evschema.schema import ORDER_V1, ORDER_V2, ORDER_V3, Schema, SchemaError


TYPE_NAMES = ("str", "int", "float", "bool", "list", "dict")
FIELD_POOL = ["a", "b", "c", "d", "e"]


def naive_check(old, new):
    """与生产实现同规则的朴素重写：逐字段扫描，理由顺序固定。"""
    reasons = []
    if old.name != new.name:
        return False, ["schema name mismatch: %s != %s" % (old.name, new.name)]

    renames = new.renames
    for source in renames:
        if source not in old.fields:
            reasons.append("rename source missing in old schema: %s" % source)

    claimed = set()
    for source, target in renames.items():
        if target not in new.fields:
            reasons.append("rename target missing in new schema: %s" % target)
            continue
        if source in old.fields and source in new.fields:
            reasons.append("rename source still present in new schema: %s" % source)
        if target not in old.fields:
            claimed.add(target)
        else:
            reasons.append("rename target already exists in old schema: %s" % target)

    for source, target in renames.items():
        if source not in old.fields or target not in new.fields:
            continue
        if old.fields[source] != new.fields[target]:
            reasons.append(
                "renamed field %s changes type %s -> %s"
                % (source, old.fields[source], new.fields[target])
            )
        if source not in old.required and target in new.required:
            reasons.append(
                "renamed optional field tightened to required: %s -> %s"
                % (source, target)
            )

    for field in old.fields:
        if field in renames:
            continue
        if field not in new.fields:
            reasons.append("field removed: %s" % field)
        elif old.fields[field] != new.fields[field]:
            reasons.append(
                "field %s changes type %s -> %s"
                % (field, old.fields[field], new.fields[field])
            )

    for field in new.required:
        if field in old.fields and field not in renames and field not in old.required:
            reasons.append("optional field tightened to required: %s" % field)

    for field in new.fields:
        if field not in old.fields and field not in claimed and field not in new.defaults:
            reasons.append("new field without default: %s" % field)

    return not reasons, reasons


def make_schema(version, fields, required=(), defaults=None, renames=None, name="e"):
    try:
        return Schema(name, version, fields, required, defaults, renames)
    except SchemaError:
        return None


def _default_of(type_name, rng):
    table = {
        "str": "",
        "int": 0,
        "float": 0.0,
        "bool": False,
        "list": [],
        "dict": {},
    }
    value = table[type_name]
    if type_name == "int" and rng.random() < 0.5:
        return rng.randrange(10)
    if type_name == "str" and rng.random() < 0.5:
        return "s"
    return value


def random_schema_pair(rng):
    """随机生成一对 (old, new)，字段池固定，版本固定为 1/2。"""
    old_fields = {}
    for field in FIELD_POOL:
        if rng.random() < 0.6:
            old_fields[field] = rng.choice(TYPE_NAMES)
    if not old_fields:
        old_fields["a"] = "str"

    old_required = tuple(f for f in old_fields if rng.random() < 0.5)
    old_defaults = {}
    for field in old_fields:
        if field not in old_required and rng.random() < 0.5:
            old_defaults[field] = _default_of(old_fields[field], rng)
    old = make_schema(1, old_fields, old_required, old_defaults)
    if old is None:
        return None

    new_fields = dict(old_fields)
    for field in list(old_fields):
        if rng.random() < 0.2:
            del new_fields[field]
    for field in FIELD_POOL:
        if field not in old_fields and rng.random() < 0.4:
            new_fields[field] = rng.choice(TYPE_NAMES)

    renames = {}
    available_targets = [f for f in new_fields if f not in old_fields]
    available_sources = [
        f for f in old_fields if f in new_fields or rng.random() < 0.5
    ]
    for source in available_sources:
        if available_targets and rng.random() < 0.3:
            target = available_targets.pop(rng.randrange(len(available_targets)))
            renames[source] = target

    new_required = tuple(
        f for f in new_fields if f not in renames.values() and rng.random() < 0.5
    )
    new_defaults = {}
    for field in new_fields:
        if field in renames.values():
            continue
        if field not in new_required and (field not in old_fields or rng.random() < 0.7):
            new_defaults[field] = _default_of(new_fields[field], rng)

    if rng.random() < 0.2:
        for field in list(new_fields):
            if field not in old_fields:
                new_fields[field] = rng.choice(TYPE_NAMES)

    new = make_schema(2, new_fields, new_required, new_defaults, renames)
    if new is None:
        return None
    return old, new


class TestCheckCompatibilityRules(unittest.TestCase):
    def test_order_chain_is_compatible(self):
        self.assertEqual(check_compatibility(ORDER_V1, ORDER_V2), (True, []))
        self.assertEqual(check_compatibility(ORDER_V2, ORDER_V3), (True, []))

    def test_removed_field_rejected(self):
        new = Schema(
            "order", 2, {"order_id": "str", "note": "str"},
            required=("order_id",), defaults={"note": ""},
        )
        ok, reasons = check_compatibility(ORDER_V1, new)
        self.assertFalse(ok)
        self.assertIn("field removed: amount", reasons)

    def test_type_change_rejected(self):
        new = Schema(
            "order", 2,
            {"order_id": "str", "amount": "str", "note": "str"},
            required=("order_id",), defaults={"amount": "0", "note": ""},
        )
        ok, reasons = check_compatibility(ORDER_V1, new)
        self.assertFalse(ok)
        self.assertTrue(any("amount changes type" in r for r in reasons))

    def test_required_field_loosened_is_allowed(self):
        new = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str"},
            required=("order_id",), defaults={"amount": 0, "note": ""},
        )
        ok, reasons = check_compatibility(ORDER_V1, new)
        self.assertTrue(ok, reasons)

    def test_optional_field_tightened_to_required_rejected(self):
        old = Schema(
            "e", 1, {"a": "str", "b": "str"},
            required=("a",), defaults={"b": ""},
        )
        new = Schema(
            "e", 2, {"a": "str", "b": "str"},
            required=("a", "b"), defaults={"b": ""},
        )
        ok, reasons = check_compatibility(old, new)
        self.assertFalse(ok)
        self.assertIn("optional field tightened to required: b", reasons)

    def test_new_field_requires_default(self):
        new = Schema(
            "order", 2,
            {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
            required=("order_id", "amount"), defaults={"note": ""},
        )
        ok, reasons = check_compatibility(ORDER_V1, new)
        self.assertFalse(ok)
        self.assertIn("new field without default: channel", reasons)

    def test_rename_with_changed_type_rejected(self):
        old = Schema("e", 1, {"a": "str", "b": "int"}, required=("a", "b"))
        new = Schema(
            "e", 2, {"a": "str", "c": "str"},
            required=("a",), renames={"b": "c"},
        )
        ok, reasons = check_compatibility(old, new)
        self.assertFalse(ok)
        self.assertTrue(any("renamed field b changes type" in r for r in reasons))
        self.assertNotIn("field removed: b", reasons)

    def test_rename_loosening_required_is_allowed(self):
        old = Schema("e", 1, {"a": "int"}, required=("a",))
        new = Schema("e", 2, {"b": "int"}, renames={"a": "b"})
        self.assertEqual(check_compatibility(old, new), (True, []))

    def test_rename_tightening_optional_to_required_rejected(self):
        old = Schema(
            "e", 1, {"a": "str", "b": "str"},
            required=("a",), defaults={"b": ""},
        )
        new = Schema(
            "e", 2, {"a": "str", "c": "str"},
            required=("a", "c"), renames={"b": "c"},
        )
        ok, reasons = check_compatibility(old, new)
        self.assertFalse(ok)
        self.assertIn(
            "renamed optional field tightened to required: b -> c", reasons
        )

    def test_name_mismatch_short_circuits(self):
        other = Schema("other", 2, {"x": "str"}, required=("x",))
        ok, reasons = check_compatibility(ORDER_V1, other)
        self.assertFalse(ok)
        self.assertEqual(reasons, ["schema name mismatch: order != other"])


class TestRandomDifferential(unittest.TestCase):
    def test_random_pairs_match_naive_oracle(self):
        rng = random.Random(20260921)
        compared = 0
        compatible_seen = 0
        for _ in range(4000):
            pair = random_schema_pair(rng)
            if pair is None:
                continue
            old, new = pair
            expected = naive_check(old, new)
            actual = check_compatibility(old, new)
            self.assertEqual(actual, expected)
            compared += 1
            if actual[0]:
                compatible_seen += 1
        self.assertGreater(compared, 1000)
        self.assertGreater(compatible_seen, 20)

    def test_random_compatible_pair_round_trips_through_step_plan(self):
        rng = random.Random(97531)
        checked = 0
        for _ in range(4000):
            pair = random_schema_pair(rng)
            if pair is None:
                continue
            old, new = pair
            ok, _ = check_compatibility(old, new)
            if not ok:
                continue
            data = {}
            for field in old.fields:
                if field in old.required or rng.random() < 0.7:
                    data[field] = _default_of(old.fields[field], rng)
            if old.validate(data):
                continue
            plan = StepPlan(old, new)
            upgraded = plan.upgrade(dict(data))
            self.assertEqual(new.validate(upgraded), [], upgraded)
            downgraded = plan.downgrade(dict(upgraded))
            for field, value in data.items():
                self.assertEqual(downgraded.get(field), value)
            checked += 1
        self.assertGreater(checked, 20)


if __name__ == "__main__":
    unittest.main()
