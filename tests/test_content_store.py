"""内容寻址、回收与完整性的新行为测试。

与 test_store.py 的旧契约测试互补：去重、gc/stats、回收失败记账重试、
盘上损坏检测、启动半成品清扫、对拍随机一致性与多线程同内容写。
"""

import os
import random
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from blobvault import ObjectStore, ObjectCorrupted, ObjectNotFound
from blobvault import content


class ContentStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="blobvault-cas-")
        self.store = ObjectStore(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _object_path(self, data):
        return content.object_path(self.root, content.digest_of(data))


class TestDeduplication(ContentStoreTestCase):
    def test_same_bytes_one_object_many_names(self):
        payload = b"same contract body" * 10
        rel1 = self.store.put("a1", payload)
        rel2 = self.store.put("a2", payload)
        self.assertEqual(rel1, rel2)
        stats = self.store.stats()
        self.assertEqual(stats["objects"], 1)
        self.assertEqual(stats["names"], 2)
        self.assertEqual(stats["bytes"], len(payload))
        self.assertEqual(self.store.get("a1"), payload)
        self.assertEqual(self.store.get("a2"), payload)

    def test_distinct_bytes_distinct_objects(self):
        self.store.put("a", b"v1")
        self.store.put("b", b"v2-different")
        stats = self.store.stats()
        self.assertEqual(stats["objects"], 2)
        self.assertEqual(stats["names"], 2)

    def test_overwrite_name_drops_old_reference(self):
        self.store.put("doc", b"version-one-body")
        self.store.put("doc", b"version-two-body-longer")
        self.assertEqual(self.store.get("doc"), b"version-two-body-longer")
        self.assertEqual(self.store.list(), ["doc"])

    def test_2000_names_of_64k_use_under_two_megabytes(self):
        payload = bytes((i * 7 + 3) & 0xFF for i in range(64 * 1024))
        for i in range(2000):
            self.store.put("n%04d" % i, payload)
        stats = self.store.stats()
        self.assertEqual(stats["objects"], 1)
        self.assertEqual(stats["names"], 2000)
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for fn in files:
                total += os.path.getsize(os.path.join(dirpath, fn))
        self.assertLessEqual(
            total,
            2 * 1024 * 1024,
            "2000 个名字占用 %d 字节，超过两兆" % total,
        )
        for i in range(0, 2000, 97):
            self.assertEqual(self.store.get("n%04d" % i), payload)


class TestGarbageCollection(ContentStoreTestCase):
    def test_delete_keeps_object_until_gc(self):
        payload = b"collect me later"
        self.store.put("k", payload)
        obj = self._object_path(payload)
        self.assertTrue(os.path.exists(obj))
        self.assertTrue(self.store.delete("k"))
        self.assertTrue(os.path.exists(obj))
        self.assertEqual(self.store.stats()["objects"], 1)
        result = self.store.gc()
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["freed_bytes"], len(payload))
        self.assertFalse(os.path.exists(obj))
        self.assertEqual(self.store.stats()["objects"], 0)

    def test_gc_keeps_objects_still_referenced(self):
        shared = b"shared by two names"
        self.store.put("a", shared)
        self.store.put("b", shared)
        self.store.delete("a")
        result = self.store.gc()
        self.assertEqual(result["removed"], 0)
        self.assertEqual(self.store.get("b"), shared)

    def test_gc_is_idempotent_on_empty_store(self):
        self.assertEqual(
            self.store.gc(),
            {"removed": 0, "freed_bytes": 0, "failed": 0, "pending": 0},
        )

    def test_gc_works_after_reopen(self):
        payload = b"persisted orphan"
        self.store.put("p", payload)
        obj = self._object_path(payload)
        self.store.delete("p")
        reopened = ObjectStore(self.root)
        self.assertTrue(os.path.exists(obj))
        self.assertEqual(reopened.gc()["removed"], 1)
        self.assertFalse(os.path.exists(obj))

    def test_gc_never_touches_foreign_files(self):
        self.store.put("real", b"x")
        foreign_root = os.path.join(self.root, "notes.txt")
        with open(foreign_root, "w") as fh:
            fh.write("keep me")
        junk = os.path.join(self.root, "objects", "zz")
        os.makedirs(junk, exist_ok=True)
        foreign_obj = os.path.join(junk, "README.txt")
        with open(foreign_obj, "w") as fh:
            fh.write("not a blob")
        foreign_blob = os.path.join(junk, "deadbeef.blob")
        with open(foreign_blob, "wb") as fh:
            fh.write(b"name is not a full digest")
        self.store.delete("real")
        self.store.gc()
        self.assertTrue(os.path.exists(foreign_root))
        self.assertTrue(os.path.exists(foreign_obj))
        self.assertTrue(os.path.exists(foreign_blob))

    def _fail_blob_removal(self):
        original_remove = os.remove

        def fake_remove(path, *args, **kwargs):
            if path.endswith(".blob"):
                raise PermissionError("simulated IO failure")
            return original_remove(path, *args, **kwargs)

        return mock.patch("os.remove", side_effect=fake_remove)

    def test_failed_reclamation_is_bookkept_and_retried(self):
        payload = b"retry me"
        self.store.put("r", payload)
        obj = self._object_path(payload)
        digest = content.digest_of(payload)
        self.store.delete("r")

        with self._fail_blob_removal():
            result = self.store.gc()
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertTrue(os.path.exists(obj))
        ledger = content.load_ledger(self.root)
        self.assertIn(digest, ledger)
        self.assertEqual(ledger[digest]["attempts"], 1)

        with self._fail_blob_removal():
            result = self.store.gc()
        self.assertEqual(result["pending"], 1)
        self.assertEqual(
            content.load_ledger(self.root)[digest]["attempts"], 2
        )

        result = self.store.gc()
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["pending"], 0)
        self.assertFalse(os.path.exists(obj))
        self.assertFalse(
            os.path.exists(os.path.join(self.root, content.GC_LEDGER))
        )

    def test_ledger_survives_reopen(self):
        payload = b"across restart"
        self.store.put("r", payload)
        obj = self._object_path(payload)
        digest = content.digest_of(payload)
        self.store.delete("r")
        with self._fail_blob_removal():
            self.store.gc()
        reopened = ObjectStore(self.root)
        result = reopened.gc()
        self.assertEqual(result["removed"], 1)
        self.assertFalse(os.path.exists(obj))
        self.assertNotIn(digest, content.load_ledger(self.root))

    def test_re_referenced_object_is_canceled_from_ledger(self):
        payload = b"wanted again"
        self.store.put("a", payload)
        self.store.put("b", payload)
        obj = self._object_path(payload)
        self.store.delete("a")
        self.store.delete("b")
        with self._fail_blob_removal():
            self.store.gc()
        self.store.put("a", payload)
        result = self.store.gc()
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["pending"], 0)
        self.assertTrue(os.path.exists(obj))
        self.assertEqual(self.store.get("a"), payload)


class TestIntegrity(ContentStoreTestCase):
    def test_tampered_object_raises_and_not_returned(self):
        payload = b"integrity matters a lot"
        self.store.put("doc", payload)
        with open(self._object_path(payload), "r+b") as fh:
            fh.seek(0)
            fh.write(b"X")
        with self.assertRaises(ObjectCorrupted):
            self.store.get("doc")

    def test_truncated_object_raises(self):
        payload = b"truncation is corruption too" * 4
        self.store.put("doc", payload)
        path = self._object_path(payload)
        os.truncate(path, len(payload) - 3)
        with self.assertRaises(ObjectCorrupted):
            self.store.get("doc")

    def test_missing_object_for_name_raises(self):
        payload = b"where did the bytes go"
        self.store.put("doc", payload)
        os.unlink(self._object_path(payload))
        with self.assertRaises(ObjectCorrupted):
            self.store.get("doc")

    def test_put_repairs_corrupted_slot(self):
        payload = b"repair this slot please" * 3
        self.store.put("doc", payload)
        path = self._object_path(payload)
        with open(path, "wb") as fh:
            fh.write(b"garbage")
        with self.assertRaises(ObjectCorrupted):
            self.store.get("doc")
        self.store.put("doc", payload)
        self.assertEqual(self.store.get("doc"), payload)
        self.assertEqual(self.store.stats()["objects"], 1)


class TestStartupSweep(ContentStoreTestCase):
    def test_reopen_sweeps_only_own_tmp_leftovers(self):
        self.store.put("keep", b"v")
        objs = os.path.join(self.root, "objects")
        shard = os.path.join(objs, content.digest_of(b"v")[:2])
        dead_pid = 999999
        stale_ts = 1
        leftover_name = ".bvtmp-%d-111-%d.part" % (dead_pid, stale_ts)
        own_tmp = os.path.join(shard, leftover_name)
        own_root_tmp = os.path.join(self.root, ".bvtmp-%d-112-%d.part"
                                   % (dead_pid, stale_ts))
        old_fmt = os.path.join(shard, ".bvtmp-old-style.part")
        for p in (own_tmp, own_root_tmp, old_fmt):
            with open(p, "wb") as fh:
                fh.write(b"half")
            old_ts = 0  # 远古 mtime，超过在途宽限
            os.utime(p, (old_ts, old_ts))
        # 刚产生、pid 仍存活的临时文件绝不能被扫掉。
        fresh = os.path.join(
            shard,
            ".bvtmp-%d-222-%d.part" % (os.getpid(), int(time.time())),
        )
        with open(fresh, "wb") as fh:
            fh.write(b"live write")
        foreign = os.path.join(shard, ".bvkeep-alike")
        with open(foreign, "wb") as fh:
            fh.write(b"not ours")

        ObjectStore(self.root)  # 重开即清扫

        self.assertFalse(os.path.exists(own_tmp))
        self.assertFalse(os.path.exists(old_fmt))
        self.assertTrue(os.path.exists(fresh))
        self.assertTrue(os.path.exists(foreign))
        self.assertEqual(ObjectStore(self.root).get("keep"), b"v")

    def test_sweep_after_real_simulated_crash(self):
        # 端到端：构造一个本进程刚写的临时名，再以“已死 pid + 陈旧
        # 时间戳”的同名遗留模拟被杀进程，重开必须清掉。
        leftover = os.path.join(
            self.root,
            ".bvtmp-%d-333-%d.part"
            % (999999, int(time.time()) - 3600),
        )
        with open(leftover, "wb") as fh:
            fh.write(b"crashed")
        self.assertEqual(ObjectStore(self.root).stats()["names"], 0)
        self.assertFalse(os.path.exists(leftover))


class TestConcurrentSameContent(ContentStoreTestCase):
    def test_eight_threads_writing_same_bytes(self):
        payload = bytes((i * 13 + 1) & 0xFF for i in range(64 * 1024))
        errors = []

        def worker(tid):
            try:
                for j in range(100):
                    self.store.put("t%dn%03d" % (tid, j), payload)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        stats = self.store.stats()
        self.assertEqual(stats["objects"], 1)
        self.assertEqual(stats["names"], 800)
        self.assertEqual(stats["bytes"], len(payload))
        for t in range(8):
            for j in range(100):
                self.assertEqual(
                    self.store.get("t%dn%03d" % (t, j)), payload
                )


class NaiveReferenceStore:
    """一名一文件的最朴素内存实现，作为对拍参照。"""

    def __init__(self):
        self._data = {}

    def put(self, name, data):
        self._data[name] = bytes(data)

    def get(self, name):
        if name not in self._data:
            raise ObjectNotFound(name)
        return self._data[name]

    def delete(self, name):
        if name in self._data:
            del self._data[name]
            return True
        return False

    def list(self):
        return sorted(self._data)


class TestDifferentialAgainstNaiveStore(ContentStoreTestCase):
    def test_random_operations_match_naive_store(self):
        rng = random.Random(20260921)
        names = ["n%02d" % i for i in range(20)]
        shared = b"same contract body" * 64
        payloads = [
            b"",
            b"small",
            shared,
            bytes(range(256)),
            shared,  # 与上一份完全相同，专门压去重路径
            b"other-uniq" * 50,
        ]
        naive = NaiveReferenceStore()

        def same_read(name):
            try:
                expected = naive.get(name)
            except ObjectNotFound:
                with self.assertRaises(ObjectNotFound):
                    self.store.get(name)
                return
            self.assertEqual(self.store.get(name), expected)

        for round_no in range(400):
            roll = rng.random()
            if roll < 0.45:
                name = rng.choice(names)
                data = rng.choice(payloads)
                naive.put(name, data)
                self.store.put(name, data)
            elif roll < 0.75:
                same_read(rng.choice(names))
            elif roll < 0.9:
                name = rng.choice(names)
                self.assertEqual(
                    self.store.delete(name), naive.delete(name)
                )
            else:
                self.assertEqual(self.store.list(), naive.list())
            if round_no % 50 == 49:
                self.store.gc()
                for name in naive.list():
                    same_read(name)

        self.assertEqual(self.store.list(), naive.list())
        for name in naive.list():
            same_read(name)

        for name in naive.list():
            self.assertTrue(self.store.delete(name))
        result = self.store.gc()
        self.assertEqual(result["failed"], 0)
        self.assertEqual(self.store.stats()["objects"], 0)


if __name__ == "__main__":
    unittest.main()
