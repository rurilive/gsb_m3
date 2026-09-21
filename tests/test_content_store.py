"""内容寻址改造后的新行为测试（不动 test_store.py 里的旧契约）。

覆盖：相同字节去重、删除只减引用 + gc 回收、回收失败记账重试、
对象改坏读回必报错、临时文件原子写与启动清扫、gc/stats、八线程
并发写同一份内容，以及与"一名一文件"朴素实现的随机几百轮对拍。
"""

import hashlib
import os
import random
import shutil
import tempfile
import threading
import unittest

from blobvault import ObjectStore
from blobvault.errors import CorruptObject, ObjectNotFound


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def walk_usage(root):
    """os.walk 统计目录下所有文件的真实占用（含引用与账本）。"""
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            total += os.path.getsize(os.path.join(dirpath, fn))
    return total


def count_tmp_files(root):
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith(".bvtmp"):
                total += 1
    return total


class ContentStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="blobvault-cas-")
        self.store = ObjectStore(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestDeduplication(ContentStoreTestCase):
    def test_same_bytes_one_object(self):
        payload = b"same contract body " * 64
        rel1 = self.store.put("contract-a", payload)
        rel2 = self.store.put("contract-b", payload)
        self.assertEqual(rel1, rel2)
        stats = self.store.stats()
        self.assertEqual(stats["objects"], 1)
        self.assertEqual(stats["names"], 2)
        self.assertEqual(stats["bytes"], len(payload))
        with open(os.path.join(self.root, rel1), "rb") as fh:
            self.assertEqual(fh.read(), payload)

    def test_2000_names_of_64k_stay_under_2mb(self):
        payload = bytes((i * 7 + 3) & 0xFF for i in range(64 * 1024))
        for i in range(2000):
            self.store.put("name%04d" % i, payload)
        for i in range(2000):
            self.assertEqual(self.store.get("name%04d" % i), payload)
        self.assertEqual(self.store.stats()["objects"], 1)
        usage = walk_usage(self.root)
        self.assertLess(usage, 2 * 1024 * 1024, "目录占用 %d 字节" % usage)

    def test_overwrite_repoints_and_gc_reclaims_old(self):
        old, new = b"version-one", b"version-two-totally-different"
        self.store.put("doc", old)
        old_path = None
        for dp, _fns, files in os.walk(os.path.join(self.root, "objects")):
            for fn in files:
                old_path = os.path.join(dp, fn)
        self.store.put("doc", new)
        self.assertEqual(self.store.get("doc"), new)
        self.assertEqual(self.store.stats()["objects"], 2)
        report = self.store.gc()
        self.assertEqual(report["removed"], 1)
        self.assertEqual(report["bytes"], len(old))
        self.assertFalse(os.path.exists(old_path))
        self.assertEqual(self.store.stats()["objects"], 1)

    def test_empty_and_distinct_payloads(self):
        self.store.put("e1", b"")
        self.store.put("e2", b"")
        self.store.put("x", b"x")
        self.assertEqual(self.store.stats()["objects"], 2)
        self.assertEqual(self.store.get("e1"), b"")


class TestDeleteAndGc(ContentStoreTestCase):
    def test_delete_only_drops_reference(self):
        self.store.put("keep", b"shared")
        self.store.put("drop", b"shared")
        self.assertTrue(self.store.delete("drop"))
        self.assertFalse(self.store.delete("drop"))
        with self.assertRaises(ObjectNotFound):
            self.store.get("drop")
        self.assertEqual(self.store.stats()["objects"], 1)
        self.assertEqual(self.store.get("keep"), b"shared")
        self.assertEqual(self.store.gc()["removed"], 0)

    def test_gc_reclaims_unreferenced(self):
        self.store.put("a", b"aaa-payload")
        self.store.put("b", b"bbb-payload")
        self.store.delete("b")
        report = self.store.gc()
        self.assertEqual(report["removed"], 1)
        self.assertEqual(report["bytes"], len(b"bbb-payload"))
        self.assertEqual(report["pending"], 0)
        self.assertEqual(self.store.get("a"), b"aaa-payload")
        self.assertEqual(
            self.store.gc(),
            {"removed": 0, "bytes": 0, "retry": 0, "pending": 0},
        )

    def test_gc_empty_store(self):
        self.assertEqual(
            self.store.gc(),
            {"removed": 0, "bytes": 0, "retry": 0, "pending": 0},
        )
        self.assertEqual(self.store.stats(),
                         {"objects": 0, "names": 0, "bytes": 0})

    def _force_object_unlink_failure(self, digest):
        real_remove = os.remove

        def failing_remove(path, *args, **kwargs):
            if os.path.basename(path) == digest:
                raise PermissionError("simulated unlink failure")
            return real_remove(path, *args, **kwargs)

        return real_remove, failing_remove

    def test_gc_failure_is_bookkept_and_retried(self):
        payload = b"will not delete easily"
        digest = sha256_hex(payload)
        self.store.put("temp", payload)
        self.store.delete("temp")

        real_remove, failing_remove = self._force_object_unlink_failure(digest)
        os.remove = failing_remove
        try:
            report = self.store.gc()
        finally:
            os.remove = real_remove
        self.assertEqual(report["removed"], 0)
        self.assertEqual(report["pending"], 1)

        ledger = os.path.join(self.root, "gc", "pending")
        self.assertTrue(os.path.isfile(ledger))
        with open(ledger) as fh:
            self.assertEqual(fh.read().strip(), digest)
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.root, "objects", digest[:2], digest))
        )

        report2 = self.store.gc()
        self.assertEqual(report2["removed"], 1)
        self.assertEqual(report2["retry"], 1)
        self.assertEqual(report2["pending"], 0)
        self.assertFalse(os.path.exists(ledger))

    def test_pending_survives_reopen_and_then_retried(self):
        payload = b"survive restart debt"
        digest = sha256_hex(payload)
        self.store.put("temp", payload)
        self.store.delete("temp")

        real_remove, failing_remove = self._force_object_unlink_failure(digest)
        os.remove = failing_remove
        try:
            self.assertEqual(self.store.gc()["pending"], 1)
        finally:
            os.remove = real_remove

        reopened = ObjectStore(self.root)
        report = reopened.gc()
        self.assertEqual(report["removed"], 1)
        self.assertEqual(report["retry"], 1)
        self.assertEqual(report["pending"], 0)

    def test_pending_canceled_when_referenced_again(self):
        payload = b"coming back"
        digest = sha256_hex(payload)
        self.store.put("temp", payload)
        self.store.delete("temp")

        real_remove, failing_remove = self._force_object_unlink_failure(digest)
        os.remove = failing_remove
        try:
            self.assertEqual(self.store.gc()["pending"], 1)
        finally:
            os.remove = real_remove

        self.store.put("back", payload)
        report = self.store.gc()
        self.assertEqual(report["removed"], 0)
        self.assertEqual(report["pending"], 0)
        self.assertFalse(
            os.path.exists(os.path.join(self.root, "gc", "pending")))
        self.assertEqual(self.store.get("back"), payload)

    def test_gc_raises_on_corrupt_ref_and_keeps_everything(self):
        self.store.put("good", b"good bytes")
        self.store.put("bad-ref", b"other bytes")
        ref_path = os.path.join(self.root, "index", "ba", "bad-ref.ref")
        with open(ref_path, "wb") as fh:
            fh.write(b"not a digest at all\n")
        objects_before = []
        for dp, _fns, fns in os.walk(os.path.join(self.root, "objects")):
            objects_before.extend(os.path.join(dp, f) for f in fns)
        with self.assertRaises(CorruptObject):
            self.store.gc()
        for ap in objects_before:
            self.assertTrue(os.path.exists(ap))
        self.assertEqual(self.store.get("good"), b"good bytes")

    def test_gc_ignores_foreign_files(self):
        self.store.put("real", b"v")
        with open(os.path.join(self.root, "notes.txt"), "w") as fh:
            fh.write("ops scratch")
        junk = os.path.join(self.root, "objects", "zz")
        os.makedirs(junk, exist_ok=True)
        with open(os.path.join(junk, "README.txt"), "w") as fh:
            fh.write("leave me alone")
        self.store.gc()
        self.assertTrue(os.path.isfile(os.path.join(self.root, "notes.txt")))
        self.assertTrue(os.path.isfile(os.path.join(junk, "README.txt")))


class TestIntegrity(ContentStoreTestCase):
    def test_tampered_object_raises_on_get(self):
        rel = self.store.put("contract", b"original four")
        with open(os.path.join(self.root, rel), "r+b") as fh:
            fh.seek(0)
            fh.write(b"X")
        with self.assertRaises(CorruptObject):
            self.store.get("contract")

    def test_missing_object_raises_on_get(self):
        rel = self.store.put("contract", b"original four")
        os.remove(os.path.join(self.root, rel))
        with self.assertRaises(CorruptObject):
            self.store.get("contract")

    def test_tampered_ref_raises_on_get(self):
        self.store.put("contract", b"original four")
        ref_path = os.path.join(self.root, "index", "co", "contract.ref")
        with open(ref_path, "wb") as fh:
            fh.write(b"z" * 64)
        with self.assertRaises(CorruptObject):
            self.store.get("contract")


class TestAtomicWritesAndRecovery(ContentStoreTestCase):
    def test_no_tmp_left_after_writes(self):
        for i in range(20):
            self.store.put("key%02d" % i, b"payload-%d" % i)
        self.assertEqual(count_tmp_files(self.root), 0)

    def test_sweep_removes_only_own_half_files_on_open(self):
        for area, shard in (
            ("objects", "aa"),
            ("index", "bb"),
            ("gc", None),
        ):
            directory = (
                os.path.join(self.root, area, shard)
                if shard else os.path.join(self.root, area)
            )
            os.makedirs(directory, exist_ok=True)
            with open(
                os.path.join(directory, ".deadbeef.%s.bvtmp" % ("x" * 8)),
                "wb",
            ) as fh:
                fh.write(b"half-written")
        foreign_note = os.path.join(self.root, "notes.txt")
        with open(foreign_note, "w") as fh:
            fh.write("ops scratch")
        foreign_dir = os.path.join(self.root, "objects", "zz")
        os.makedirs(foreign_dir, exist_ok=True)
        with open(os.path.join(foreign_dir, "README.txt"), "w") as fh:
            fh.write("not ours")

        ObjectStore(self.root)

        self.assertEqual(count_tmp_files(self.root), 0)
        self.assertTrue(os.path.isfile(foreign_note))
        self.assertTrue(
            os.path.isfile(os.path.join(foreign_dir, "README.txt")))

    def test_data_survives_reopen_after_many_writes(self):
        payload = b"persistence check " * 100
        for i in range(30):
            self.store.put("doc%02d" % i, payload)
        reopened = ObjectStore(self.root)
        self.assertEqual(reopened.stats()["objects"], 1)
        self.assertEqual(
            sorted(reopened.list()),
            sorted("doc%02d" % i for i in range(30)),
        )
        self.assertEqual(reopened.get("doc29"), payload)


class TestConcurrency(ContentStoreTestCase):
    def test_eight_threads_same_content(self):
        payload = bytes((i * 13 + 1) & 0xFF for i in range(64 * 1024))
        errors = []

        def worker(tid):
            try:
                for _round in range(50):
                    name = "thread%02d" % tid
                    self.store.put(name, payload)
                    if self.store.get(name) != payload:
                        raise AssertionError("读回内容不一致")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.store.stats()["objects"], 1)
        for t in range(8):
            self.assertEqual(self.store.get("thread%02d" % t), payload)
        ObjectStore(self.root)
        self.assertEqual(count_tmp_files(self.root), 0)

    def test_concurrent_overwrite_never_corrupts(self):
        payloads = [b"A" * 4096, b"B" * 4096]
        errors = []

        def worker(payload):
            try:
                for _ in range(100):
                    self.store.put("shared", payload)
                    got = self.store.get("shared")
                    if got not in payloads:
                        raise AssertionError("读到半成品字节")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(payloads[i % 2],))
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.store.gc()


class NaiveNameFileStore:
    """验收基线：改造前的"一名一文件"朴素实现，独立目录布局。"""

    def __init__(self, root):
        self.root = root
        self.model = {}

    def put(self, name, data):
        path = os.path.join(self.root, "names", name[:2].ljust(2, "_"))
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, name + ".blob"), "wb") as fh:
            fh.write(data)
        self.model[name] = bytes(data)

    def get(self, name):
        if name not in self.model:
            raise KeyError(name)
        return self.model[name]

    def delete(self, name):
        existed = name in self.model
        self.model.pop(name, None)
        return existed

    def list(self):
        return sorted(self.model)


class TestDifferentialAgainstNaive(unittest.TestCase):
    def test_random_ops_match_naive_for_hundreds_of_rounds(self):
        cas_root = tempfile.mkdtemp(prefix="blobvault-diff-cas-")
        naive_root = tempfile.mkdtemp(prefix="blobvault-diff-naive-")
        rng = random.Random(1720092118)
        try:
            cas = ObjectStore(cas_root)
            naive = NaiveNameFileStore(naive_root)
            names = ["n%02d" % i for i in range(12)]
            payloads = [
                b"",
                b"tiny",
                b"contract body v1 " * 64,
                b"contract body v1 " * 64,  # 故意重复，制造去重
                bytes(rng.getrandbits(8) for _ in range(2048)),
                bytes((i * 7) & 0xFF for i in range(4096)),
            ]

            for round_no in range(400):
                name = rng.choice(names)
                action = rng.random()
                if action < 0.45:
                    data = rng.choice(payloads)
                    cas.put(name, data)
                    naive.put(name, data)
                elif action < 0.8:
                    if name in naive.model:
                        self.assertEqual(cas.get(name), naive.get(name))
                    else:
                        with self.assertRaises(ObjectNotFound):
                            cas.get(name)
                elif action < 0.92:
                    self.assertEqual(cas.delete(name), naive.delete(name))
                else:
                    self.assertEqual(cas.list(), naive.list())

                if round_no % 50 == 49:
                    cas.gc()
                    for existing in naive.list():
                        self.assertEqual(
                            cas.get(existing), naive.get(existing))
                    cas = ObjectStore(cas_root)

            self.assertEqual(cas.list(), naive.list())
            for name in naive.list():
                self.assertEqual(cas.get(name), naive.get(name))
            stats = cas.stats()
            self.assertEqual(stats["names"], len(naive.list()))
            expected_objects = {
                sha256_hex(data) for data in naive.model.values()
            }
            self.assertEqual(stats["objects"], len(expected_objects))
        finally:
            shutil.rmtree(cas_root, ignore_errors=True)
            shutil.rmtree(naive_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
