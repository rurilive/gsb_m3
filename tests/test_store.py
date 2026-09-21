"""ObjectStore 现有行为的锁定测试。

这些用例描述的是当前对外契约：名字校验规则、put/get/delete/list 的
语义、二进制往返、返回值约定。改动实现时它们必须原样通过。
"""

import os
import pathlib
import shutil
import tempfile
import threading
import unittest

from blobvault import ObjectStore
from blobvault.errors import InvalidKey, ObjectNotFound


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="blobvault-test-")
        self.store = ObjectStore(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestPutGet(StoreTestCase):
    def test_roundtrip_bytes(self):
        self.store.put("report", b"hello blobvault")
        self.assertEqual(self.store.get("report"), b"hello blobvault")

    def test_binary_payload_with_nul_roundtrips(self):
        payload = b"\x00\x01\xff\r\n\x00binary\x00"
        self.store.put("blob-1", payload)
        self.assertEqual(self.store.get("blob-1"), payload)

    def test_empty_payload_roundtrips(self):
        self.store.put("empty", b"")
        self.assertEqual(self.store.get("empty"), b"")
        self.assertIn("empty", self.store.list())

    def test_overwrite_same_name(self):
        self.store.put("cfg", b"v1")
        self.store.put("cfg", b"v2")
        self.assertEqual(self.store.get("cfg"), b"v2")
        self.assertEqual(self.store.list().count("cfg"), 1)

    def test_put_returns_relative_path_that_holds_bytes(self):
        payload = b"payload for the download route"
        rel = self.store.put("dl-me", payload)
        self.assertFalse(os.path.isabs(rel))
        path = os.path.join(self.root, rel)
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), payload)

    def test_put_rejects_str_payload(self):
        with self.assertRaises(TypeError):
            self.store.put("text", "not bytes")

    def test_get_unknown_name_raises(self):
        with self.assertRaises(ObjectNotFound) as ctx:
            self.store.get("nope")
        self.assertIsInstance(ctx.exception, KeyError)

    def test_root_created_on_first_write(self):
        root = os.path.join(self.root, "nested", "data")
        store = ObjectStore(root)
        store.put("x1", b"v")
        self.assertTrue(os.path.isdir(root))
        self.assertEqual(store.get("x1"), b"v")

    def test_root_accepts_pathlike(self):
        store = ObjectStore(pathlib.Path(self.root))
        store.put("p1", b"v")
        self.assertEqual(store.get("p1"), b"v")


class TestKeyRules(StoreTestCase):
    def test_accepts_letters_digits_dots_dashes_underscores(self):
        for name in ("a", "A9", "archive.tar.gz", "user_1-2", "x" * 64):
            self.store.put(name, name.encode())
            self.assertEqual(self.store.get(name), name.encode())

    def test_rejects_invalid_names(self):
        bad = ("", "a/b", "..", ".hidden", "a b", "-lead", "_lead",
               "x" * 65, "附件", "a\\b")
        for name in bad:
            with self.assertRaises(InvalidKey, msg=repr(name)):
                self.store.put(name, b"v")

    def test_names_are_case_sensitive(self):
        self.store.put("Abc", b"upper")
        self.store.put("abc", b"lower")
        self.assertEqual(self.store.get("Abc"), b"upper")
        self.assertEqual(self.store.get("abc"), b"lower")
        self.assertEqual(self.store.list(), ["Abc", "abc"])


class TestDeleteList(StoreTestCase):
    def test_delete_reports_whether_it_removed(self):
        self.store.put("tmp", b"v")
        self.assertTrue(self.store.delete("tmp"))
        self.assertFalse(self.store.delete("tmp"))

    def test_deleted_name_is_gone(self):
        self.store.put("gone", b"v")
        self.store.delete("gone")
        with self.assertRaises(ObjectNotFound):
            self.store.get("gone")
        self.assertNotIn("gone", self.store.list())

    def test_list_is_sorted_and_empty_when_new(self):
        self.assertEqual(self.store.list(), [])
        for name in ("b2", "a1", "c3"):
            self.store.put(name, b"v")
        self.assertEqual(self.store.list(), ["a1", "b2", "c3"])

    def test_list_ignores_foreign_files(self):
        self.store.put("real", b"v")
        with open(os.path.join(self.root, "notes.txt"), "w") as fh:
            fh.write("ops scratch file")
        junk_dir = os.path.join(self.root, "objects", "zz")
        os.makedirs(junk_dir, exist_ok=True)
        with open(os.path.join(junk_dir, "README.txt"), "w") as fh:
            fh.write("not an object")
        self.assertEqual(self.store.list(), ["real"])

    def test_data_survives_reopen(self):
        self.store.put("persist", b"v1")
        again = ObjectStore(self.root)
        self.assertEqual(again.get("persist"), b"v1")
        self.assertEqual(again.list(), ["persist"])

    def test_concurrent_puts_of_distinct_names(self):
        errors = []

        def worker(i):
            try:
                for j in range(10):
                    name = "w%d-%d" % (i, j)
                    self.store.put(name, name.encode() * 50)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.store.list()), 60)
        for i in range(6):
            for j in range(10):
                name = "w%d-%d" % (i, j)
                self.assertEqual(self.store.get(name), name.encode() * 50)


if __name__ == "__main__":
    unittest.main()
