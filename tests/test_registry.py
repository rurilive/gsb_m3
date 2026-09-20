"""SchemaRegistry 现有行为的锁定测试。"""

import unittest

from evschema.registry import SchemaRegistry
from evschema.schema import ORDER_V1, Schema, SchemaError


def _order_v2():
    """v1 之上加一个带默认值的字段。"""
    return Schema(
        "order",
        2,
        {"order_id": "str", "amount": "int", "note": "str", "channel": "str"},
        required=("order_id", "amount"),
        defaults={"note": "", "channel": "unknown"},
    )


class TestSchemaRegistry(unittest.TestCase):
    def test_register_then_get(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        self.assertIs(registry.get("order", 1), ORDER_V1)

    def test_latest_follows_highest_version(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        v2 = _order_v2()
        registry.register(v2)
        self.assertIs(registry.latest("order"), v2)

    def test_versions_are_sorted(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(_order_v2())
        self.assertEqual(registry.versions("order"), [1, 2])

    def test_versions_of_unknown_name_is_empty(self):
        self.assertEqual(SchemaRegistry().versions("order"), [])

    def test_names_and_len(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        registry.register(Schema("user", 1, {"user_id": "str"}))
        self.assertEqual(registry.names(), ["order", "user"])
        self.assertEqual(len(registry), 2)

    def test_duplicate_version_rejected(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        with self.assertRaises(SchemaError):
            registry.register(ORDER_V1)

    def test_get_unknown_version_raises(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        with self.assertRaises(SchemaError):
            registry.get("order", 9)

    def test_latest_unknown_name_raises(self):
        with self.assertRaises(SchemaError):
            SchemaRegistry().latest("order")

    def test_rejected_duplicate_leaves_registry_unchanged(self):
        registry = SchemaRegistry()
        registry.register(ORDER_V1)
        with self.assertRaises(SchemaError):
            registry.register(Schema("order", 1, {"other": "int"}))
        self.assertIs(registry.get("order", 1), ORDER_V1)


if __name__ == "__main__":
    unittest.main()
