"""WriteAheadLog 行为与磁盘格式基线。

这些断言描述的是线上已经在依赖的语义：LSN 的分配、磁盘上一条记录的字节布局、
append 返回即已落盘、重放顺序、残尾处理。重构内部实现时它们必须原样全绿。
"""
import os
import struct
import tempfile
import threading
import unittest
from unittest import mock

from walg import WriteAheadLog

HEAD = struct.Struct(">QI")


class WalCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "wal.log")

    def raw(self):
        with open(self.path, "rb") as f:
            return f.read()


class TestAppend(WalCase):
    def test_lsn_starts_at_one_and_increases(self):
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.last_lsn, 0)
            self.assertEqual(wal.append(b"a"), 1)
            self.assertEqual(wal.append(b"b"), 2)
            self.assertEqual(wal.last_lsn, 2)

    def test_read_from_returns_what_was_written(self):
        with WriteAheadLog(self.path) as wal:
            wal.append(b"a")
            lsn = wal.append(b"b")
            self.assertEqual(wal.read_from(lsn), [(lsn, b"b")])

    def test_accepts_bytearray_and_empty_payload(self):
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.append(bytearray(b"")), 1)
            self.assertEqual(wal.read_from(1), [(1, b"")])

    def test_rejects_non_bytes(self):
        with WriteAheadLog(self.path) as wal:
            for bad in ("text", 1, None):
                with self.assertRaises(TypeError):
                    wal.append(bad)


class TestDiskFormat(WalCase):
    def test_record_layout_is_stable(self):
        """[lsn:8][len:4][payload]，老文件必须还能读。"""
        with WriteAheadLog(self.path) as wal:
            wal.append(b"hello")
            wal.append(b"")
        self.assertEqual(self.raw(), HEAD.pack(1, 5) + b"hello" + HEAD.pack(2, 0))

    def test_reopen_continues_lsn(self):
        with WriteAheadLog(self.path) as wal:
            wal.append(b"a")
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.last_lsn, 1)
            self.assertEqual(wal.append(b"b"), 2)
        self.assertEqual([p for _, p in WriteAheadLog(self.path).read_from(1)],
                         [b"a", b"b"])


class TestDurability(WalCase):
    def test_append_does_not_return_before_sync(self):
        """append 返回时对应的刷盘动作必须已经发出，不许先答后刷。"""
        durables = []
        real_fsync, real_fdatasync = os.fsync, os.fdatasync

        def spy_fsync(fd):
            durables.append("fsync")
            return real_fsync(fd)

        def spy_fdatasync(fd):
            durables.append("fdatasync")
            return real_fdatasync(fd)

        with mock.patch("os.fsync", spy_fsync), \
                mock.patch("os.fdatasync", spy_fdatasync):
            with WriteAheadLog(self.path) as wal:
                for i in range(20):
                    before = len(durables)
                    wal.append(b"r%d" % i)
                    self.assertGreater(len(durables), before,
                                       "第 %d 条 append 返回前没有刷盘" % (i + 1))

    def test_acknowledged_record_is_visible_to_other_reader(self):
        with WriteAheadLog(self.path) as wal:
            lsns = [wal.append(b"durable-%d" % i) for i in range(10)]
        other = WriteAheadLog(self.path)
        self.assertEqual([l for l, _ in other.read_from(1)], lsns)
        other.close()


class TestReplay(WalCase):
    def test_replay_order_matches_write_order(self):
        with WriteAheadLog(self.path) as wal:
            lsns = [wal.append(b"%d" % i) for i in range(50)]
            got = wal.read_from(1)
        self.assertEqual([l for l, _ in got], lsns)
        self.assertEqual([p for _, p in got], [b"%d" % i for i in range(50)])

    def test_read_from_filters_by_lsn(self):
        with WriteAheadLog(self.path) as wal:
            for i in range(5):
                wal.append(b"r%d" % i)
            self.assertEqual(wal.read_from(3), [(3, b"r2"), (4, b"r3"), (5, b"r4")])

    def test_empty_log_replays_nothing(self):
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.read_from(1), [])
            self.assertEqual(wal.last_lsn, 0)

    def test_torn_tail_is_dropped_and_log_stays_writable(self):
        with WriteAheadLog(self.path) as wal:
            wal.append(b"good-1")
            wal.append(b"good-2")
        with open(self.path, "ab") as f:            # 模拟刷盘途中被杀
            f.write(HEAD.pack(3, 100) + b"half")
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.last_lsn, 2)
            self.assertEqual([p for _, p in wal.read_from(1)], [b"good-1", b"good-2"])
            self.assertEqual(wal.append(b"good-3"), 3)
            self.assertEqual([p for _, p in wal.read_from(1)],
                             [b"good-1", b"good-2", b"good-3"])


class TestConcurrentAppend(WalCase):
    def test_lsn_is_unique_and_replay_is_ordered(self):
        threads, per_thread = 8, 25
        barrier = threading.Barrier(threads)

        with WriteAheadLog(self.path) as wal:
            def worker(tag):
                barrier.wait()
                for i in range(per_thread):
                    wal.append(b"t%d-%d" % (tag, i))

            pool = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
            for t in pool:
                t.start()
            for t in pool:
                t.join()
            self.assertEqual(wal.last_lsn, threads * per_thread)
            got = wal.read_from(1)

        lsns = [l for l, _ in got]
        self.assertEqual(lsns, sorted(lsns))
        self.assertEqual(set(lsns), set(range(1, threads * per_thread + 1)))
        self.assertEqual(sorted(p for _, p in got),
                         sorted(b"t%d-%d" % (t, i)
                                for t in range(threads) for i in range(per_thread)))


if __name__ == "__main__":
    unittest.main()
