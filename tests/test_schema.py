"""Schema 与字段校验的现有行为锁定。"""

import unittest

from evschema.schema import ORDER_V1, Schema, SchemaError, type_ok


class TestTypeOk(unittest.TestCase):
    def test_bool_is_not_int(self):
        self.assertTrue(type_ok(True, "bool"))
        self.assertFalse(type_ok(True, "int"))
        self.assertTrue(type_ok(7, "int"))

    def test_int_is_not_float(self):
        self.assertTrue(type_ok(2.5, "float"))
        self.assertFalse(type_ok(2, "float"))

    def test_str_and_containers(self):
        self.assertTrue(type_ok("x", "str"))
        self.assertFalse(type_ok(1, "str"))
        self.assertTrue(type_ok([1, 2], "list"))
        self.assertTrue(type_ok({"a": 1}, "dict"))
        self.assertFalse(type_ok((1, 2), "list"))

    def test_unknown_type_name_raises(self):
        with self.assertRaises(SchemaError):
            type_ok("x", "uuid")


class TestSchemaConstruction(unittest.TestCase):
    def test_declared_fields_stay_ordered(self):
        schema = Schema("order", 1, {"b": "int", "a": "str"})
        self.assertEqual(schema.field_names(), ["b", "a"])

    def test_required_must_be_declared(self):
        with self.assertRaises(SchemaError):
            Schema("order", 1, {"a": "str"}, required=("b",))

    def test_unknown_type_name_rejected(self):
        with self.assertRaises(SchemaError):
            Schema("order", 1, {"a": "uuid"})

    def test_default_must_be_declared_and_typed(self):
        with self.assertRaises(SchemaError):
            Schema("order", 1, {"a": "str"}, defaults={"b": ""})
        with self.assertRaises(SchemaError):
            Schema("order", 1, {"a": "str"}, defaults={"a": 3})

    def test_fields_dict_is_copied(self):
        fields = {"a": "str"}
        schema = Schema("order", 1, fields)
        fields["b"] = "int"
        self.assertEqual(schema.field_names(), ["a"])


class TestValidate(unittest.TestCase):
    def test_valid_data_has_no_problems(self):
        self.assertEqual(ORDER_V1.validate({"order_id": "o-1", "amount": 900}), [])

    def test_missing_required_field(self):
        problems = ORDER_V1.validate({"order_id": "o-1"})
        self.assertEqual(problems, ["missing required field: amount"])

    def test_unknown_field(self):
        problems = ORDER_V1.validate({"order_id": "o-1", "amount": 1, "extra": 2})
        self.assertEqual(problems, ["unknown field: extra"])

    def test_wrong_type_reports_declared_and_actual(self):
        problems = ORDER_V1.validate({"order_id": "o-1", "amount": "many"})
        self.assertEqual(problems, ["field amount expects int, got str"])

    def test_bool_value_is_not_accepted_as_int(self):
        problems = ORDER_V1.validate({"order_id": "o-1", "amount": True})
        self.assertEqual(problems, ["field amount expects int, got bool"])

    def test_optional_field_may_be_absent(self):
        self.assertEqual(ORDER_V1.validate({"order_id": "o-1", "amount": 5}), [])


if __name__ == "__main__":
    unittest.main()
