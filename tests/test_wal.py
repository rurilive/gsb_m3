"""walog 掉电恢复防回归测试，四个线上现象各对应一组用例。"""

import json
import os
import struct
import tempfile
import unittest
import zlib
from unittest import mock

from walog import KVStore, WriteAheadLog


def frame(record, *, bad_crc=False):
    payload = json.dumps(record, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    head = struct.pack("<H", len(payload))
    crc = 0 if bad_crc else zlib.crc32(head + payload)
    return head + payload + struct.pack(">I", crc)


class CrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="walog-test-")

    def tearDown(self):
        if hasattr(self, "wal") and self.wal is not None:
            self.wal.close()

    # 现象 1：断电瞬间写了一半的帧不得被当成有效记录
    def test_torn_tail_with_short_crc_is_ignored(self):
        self.wal = WriteAheadLog(self.tmp)
        self.wal.append({"op": "set", "key": "k1", "value": "v1"})
        self.wal.append({"op": "set", "key": "k2", "value": "v2"})
        self.wal.close()
        self.wal = None

        seg = os.path.join(self.tmp, "wal-2.log")
        payload = b'{"op":"set","key":"ghost","value":"x","seq":99}'
        with open(seg, "ab") as f:
            f.write(struct.pack("<H", len(payload)) + payload + b"\x12\x34")

        wal = WriteAheadLog(self.tmp)
        recs = wal.replay()
        wal.close()
        self.assertEqual([r["key"] for r in recs], ["k1", "k2"])

    def test_torn_payload_is_ignored(self):
        self.wal = WriteAheadLog(self.tmp)
        self.wal.append({"op": "set", "key": "k1", "value": "v1"})
        self.wal.close()
        self.wal = None

        payload = b'{"op":"set","key":"ghost"'
        with open(os.path.join(self.tmp, "wal-2.log"), "ab") as f:
            f.write(struct.pack("<H", 40) + payload)

        wal = WriteAheadLog(self.tmp)
        recs = wal.replay()
        wal.close()
        self.assertEqual([r["key"] for r in recs], ["k1"])

    def test_corrupt_crc_frame_is_ignored(self):
        path = os.path.join(self.tmp, "wal-1.log")
        with open(path, "wb") as f:
            f.write(frame({"op": "set", "key": "ok", "value": "v", "seq": 1}))
            f.write(frame({"op": "set", "key": "bad", "value": "v", "seq": 2},
                          bad_crc=True))
        wal = WriteAheadLog(self.tmp)
        recs = wal.replay()
        wal.close()
        self.assertEqual([r["key"] for r in recs], ["ok"])

    # 现象 2：超过 255 字节的字段重启后必须还在（2B 长度头读写一致）
    def test_long_payload_survives_restart(self):
        store = KVStore(self.tmp)
        store.set("cert", "A" * 300)
        store.set("tail", "z")
        store.close()

        store2 = KVStore(self.tmp)
        applied = store2.recover()
        self.assertEqual(applied, 2)
        self.assertEqual(store2.get("cert"), "A" * 300)
        self.assertEqual(store2.get("tail"), "z")
        store2.close()

    def test_length_boundaries_255_and_256(self):
        for size in (255, 256, 4096):
            d = tempfile.mkdtemp(dir=self.tmp)
            store = KVStore(d)
            store.set("k", "x" * size)
            store.close()
            store2 = KVStore(d)
            store2.recover()
            self.assertEqual(len(store2.get("k")), size)
            store2.close()

    # 现象 3：段按编号数字序重放，wal-10 不得排在 wal-2 前面
    def test_segments_replayed_in_numeric_order(self):
        store = KVStore(self.tmp, max_segment_bytes=1)
        for i in range(1, 13):
            store.set("listen", f"v{i}")
        store.checkpoint()
        store.close()

        self.assertGreaterEqual(
            len([f for f in os.listdir(self.tmp) if f.endswith(".log")]), 12)

        store2 = KVStore(self.tmp, max_segment_bytes=1)
        store2.recover()
        self.assertEqual(store2.get("listen"), "v12")
        store2.close()

    def test_delete_then_set_replay_order(self):
        self.wal = WriteAheadLog(self.tmp, max_segment_bytes=1)
        for i in range(1, 12):
            self.wal.append({"op": "set", "key": "k", "value": f"v{i}"})
        self.wal.append({"op": "del", "key": "k"})
        self.wal.close()
        self.wal = None
        wal = WriteAheadLog(self.tmp, max_segment_bytes=1)
        recs = wal.replay()
        wal.close()
        self.assertEqual(recs[0]["value"], "v1")
        self.assertEqual(recs[-1]["op"], "del")
        self.assertEqual(recs[-2]["value"], "v11")

    # 现象 4：append 返回即落盘，不依赖 checkpoint/close
    def test_append_is_durable_without_close(self):
        store = KVStore(self.tmp)
        store.set("token", "t-1")

        store2 = KVStore(self.tmp)
        n = store2.recover()
        self.assertEqual(n, 1)
        self.assertEqual(store2.get("token"), "t-1")
        store.close()
        store2.close()

    def test_append_fsyncs_every_frame(self):
        self.wal = WriteAheadLog(self.tmp)
        with mock.patch.object(os, "fsync", wraps=os.fsync) as spy:
            self.wal.append({"op": "set", "key": "k", "value": "v"})
            self.assertGreaterEqual(spy.call_count, 1)

    def test_seq_continues_after_restart(self):
        first = WriteAheadLog(self.tmp)
        first.append({"op": "noop"})
        first.append({"op": "noop"})
        first.close()

        second = WriteAheadLog(self.tmp)
        second.replay()
        seq = second.append({"op": "noop"})
        self.assertEqual(seq, 3)
        second.close()

    def test_recover_applies_delete(self):
        store = KVStore(self.tmp)
        store.set("a", 1)
        store.delete("a")
        store.close()
        store2 = KVStore(self.tmp)
        store2.recover()
        self.assertIsNone(store2.get("a"))
        store2.close()


if __name__ == "__main__":
    unittest.main()
