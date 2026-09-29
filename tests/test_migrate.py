"""migrate 现有行为的锁定测试：固定规则的记录改写。

只覆盖当前已支持的能力，后面新增的可组合迁移链、依赖排序、回滚与校验
另开测试文件。
"""

import unittest

from schemakit import MigrationError, VERSION_KEY, migrate
from schemakit.migrate import migrate as migrate_from_module


class TestFieldRewrite(unittest.TestCase):
    def test_nickname_is_renamed_to_name(self):
        out = migrate({"nickname": "ada"})
        self.assertEqual(out["name"], "ada")
        self.assertNotIn("nickname", out)

    def test_missing_name_becomes_empty_string(self):
        out = migrate({"id": 1})
        self.assertEqual(out["name"], "")

    def test_nickname_wins_over_existing_name(self):
        out = migrate({"name": "old", "nickname": "new"})
        self.assertEqual(out["name"], "new")

    def test_other_fields_are_kept(self):
        out = migrate({"id": 7, "tags": ["a"]})
        self.assertEqual(out["id"], 7)
        self.assertEqual(out["tags"], ["a"])


class TestVersionStamp(unittest.TestCase):
    def test_version_is_stamped_to_one(self):
        self.assertEqual(migrate({"id": 1})[VERSION_KEY], 1)

    def test_existing_version_is_overwritten(self):
        self.assertEqual(migrate({"id": 1, "version": 9})[VERSION_KEY], 1)


class TestPurity(unittest.TestCase):
    def test_input_is_not_mutated(self):
        src = {"nickname": "ada"}
        migrate(src)
        self.assertEqual(src, {"nickname": "ada"})

    def test_returns_a_new_object(self):
        src = {"id": 1}
        self.assertIsNot(migrate(src), src)


class TestIllegalInput(unittest.TestCase):
    def test_non_dict_is_rejected(self):
        with self.assertRaises(MigrationError):
            migrate(["not", "a", "dict"])

    def test_none_is_rejected(self):
        with self.assertRaises(MigrationError):
            migrate(None)


class TestStableSurface(unittest.TestCase):
    def test_exported_from_package_and_module(self):
        self.assertIs(migrate, migrate_from_module)

    def test_version_key_is_a_string(self):
        self.assertEqual(VERSION_KEY, "version")


if __name__ == "__main__":
    unittest.main()
