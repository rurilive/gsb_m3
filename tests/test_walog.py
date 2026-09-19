"""walog 掉电恢复防回归测试。"""

import json
import os
import shutil
import struct
import tempfile
import unittest
import zlib

from walog import KVStore, WriteAheadLog


def frame(payload: bytes) -> bytes:
    head = struct.pack("<H", len(payload))
    return head + payload + struct.pack(">I", zlib.crc32(head + payload))


class WalTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="walog-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def subdir(self, name="d"):
        return os.path.join(self.dir, name)


class TornTailTest(WalTestCase):
    """现象 1：断电撕裂的半帧不能被当成有效记录。"""

    def test_half_frame_at_tail_is_ignored(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("k1", "v1")
        s.set("k2", "v2")
        s.checkpoint()
        s.close()
        payload = b'{"op":"set","key":"k9","value":"ghost","seq":99}'
        with open(os.path.join(d, "wal-2.log"), "ab") as f:
            f.write(struct.pack("<H", len(payload)) + payload + b"\x12\x34")
        s2 = KVStore(d)
        n = s2.recover()
        s2.close()
        self.assertEqual(n, 2)
        self.assertIsNone(s2.get("k9"))
        self.assertEqual(s2.get("k2"), "v2")

    def test_truncated_payload_is_ignored(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("k1", "v1")
        s.close()
        good = frame(b'{"op":"set","key":"k2","value":"v2","seq":2}')
        with open(os.path.join(d, "wal-1.log"), "ab") as f:
            f.write(good[: len(good) - 3])
        s2 = KVStore(d)
        n = s2.recover()
        s2.close()
        self.assertEqual(n, 1)
        self.assertIsNone(s2.get("k2"))

    def test_crc_mismatch_stops_replay(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("k1", "v1")
        s.close()
        bad = bytearray(frame(b'{"op":"set","key":"k2","value":"v2","seq":2}'))
        bad[-1] ^= 0xFF
        with open(os.path.join(d, "wal-1.log"), "ab") as f:
            f.write(bytes(bad))
        s2 = KVStore(d)
        n = s2.recover()
        s2.close()
        self.assertEqual(n, 1)

    def test_writes_after_torn_tail_are_recoverable(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("k1", "v1")
        s.close()
        with open(os.path.join(d, "wal-1.log"), "ab") as f:
            f.write(b"\x30\x30partial-garbage")
        s2 = KVStore(d)
        s2.recover()
        s2.set("k2", "v2")
        s2.close()
        s3 = KVStore(d)
        s3.recover()
        s3.close()
        self.assertEqual(s3.get("k1"), "v1")
        self.assertEqual(s3.get("k2"), "v2")


class LargeFieldTest(WalTestCase):
    """现象 2：超过 255 字节的字段重启后不能丢。"""

    def test_large_value_roundtrip(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("cert", "A" * 300)
        s.set("blob", "B" * 4096)
        s.close()
        s2 = KVStore(d)
        n = s2.recover()
        s2.close()
        self.assertEqual(n, 2)
        self.assertEqual(s2.get("cert"), "A" * 300)
        self.assertEqual(s2.get("blob"), "B" * 4096)

    def test_boundary_255_256(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("a", "x" * 200)
        s.set("b", "y" * 300)
        s.close()
        s2 = KVStore(d)
        s2.recover()
        s2.close()
        self.assertEqual(len(s2.get("a")), 200)
        self.assertEqual(len(s2.get("b")), 300)

    def test_oversize_record_rejected(self):
        wal = WriteAheadLog(self.subdir())
        with self.assertRaises(ValueError):
            wal.append({"big": "z" * 70000})
        wal.close()


class SegmentOrderTest(WalTestCase):
    """现象 3：段数超过 10 时重放顺序必须按段号，新值覆盖旧值。"""

    def test_last_write_wins_across_many_segments(self):
        d = self.subdir()
        s = KVStore(d, max_segment_bytes=1)
        for i in range(1, 13):
            s.set("listen", f"v{i}")
        s.checkpoint()
        s.close()
        self.assertGreaterEqual(
            len([f for f in os.listdir(d) if f.startswith("wal-")]), 12)
        s2 = KVStore(d, max_segment_bytes=1)
        n = s2.recover()
        s2.close()
        self.assertEqual(n, 12)
        self.assertEqual(s2.get("listen"), "v12")

    def test_segments_sorted_numerically(self):
        d = self.subdir()
        wal = WriteAheadLog(d)
        for no in (1, 2, 10, 11, 3):
            with open(os.path.join(d, f"wal-{no}.log"), "wb") as f:
                f.write(frame(json.dumps(
                    {"seq": no}, separators=(",", ":")).encode()))
        seqs = [r["seq"] for r in wal.replay()]
        wal.close()
        self.assertEqual(seqs, [1, 2, 3, 10, 11])


class DurabilityTest(WalTestCase):
    """现象 4：append 返回即落盘，不 close 直接重启也不能丢。"""

    def test_append_is_durable_without_close(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("token", "t-1")
        # 不 checkpoint、不 close，直接开新实例模拟进程被杀
        s2 = KVStore(d)
        s2.recover()
        s2.close()
        self.assertEqual(s2.get("token"), "t-1")
        s.close()  # 测试收尾再关句柄，避免 ResourceWarning

    def test_seq_continues_after_recovery(self):
        d = self.subdir()
        wal = WriteAheadLog(d)
        first = wal.append({"a": 1})
        wal.close()
        wal2 = WriteAheadLog(d)
        wal2.replay()
        second = wal2.append({"b": 2})
        wal2.close()
        self.assertEqual(second, first + 1)


class StoreBehaviorTest(WalTestCase):
    def test_delete_roundtrip(self):
        d = self.subdir()
        s = KVStore(d)
        s.set("k", "v")
        s.delete("k")
        s.close()
        s2 = KVStore(d)
        s2.recover()
        s2.close()
        self.assertIsNone(s2.get("k"))

    def test_recover_returns_applied_count(self):
        d = self.subdir()
        s = KVStore(d)
        for i in range(5):
            s.set(f"k{i}", i)
        s.close()
        s2 = KVStore(d)
        self.assertEqual(s2.recover(), 5)
        s2.close()


if __name__ == "__main__":
    unittest.main()
