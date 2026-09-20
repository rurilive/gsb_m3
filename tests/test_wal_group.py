"""组提交：并发 append 攒批刷盘、应答不早于落盘、失败整批报错、重启可续写。"""
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from walg import WriteAheadLog


class GroupCommitCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "wal.log")

    def run_concurrent(self, wal, threads=8, per_thread=25):
        barrier = threading.Barrier(threads)
        errors = []

        def worker(tag):
            barrier.wait()
            for i in range(per_thread):
                try:
                    wal.append(b"t%d-%d" % (tag, i))
                except Exception as exc:  # 收集起来统一断言
                    errors.append(exc)

        pool = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
        for t in pool:
            t.start()
        for t in pool:
            t.join()
        return threads * per_thread, errors


class TestBatching(GroupCommitCase):
    def test_concurrent_appends_share_fsyncs(self):
        """高并发下一批记录共用一次 fsync，刷盘次数远小于记录数。"""
        fsync_count = [0]
        count_lock = threading.Lock()
        real_fsync = os.fsync

        def slow_spy_fsync(fd):
            time.sleep(0.005)  # 模拟真实磁盘的刷盘延迟，让写线程有机会排队
            with count_lock:
                fsync_count[0] += 1
            return real_fsync(fd)

        with mock.patch("os.fsync", slow_spy_fsync):
            with WriteAheadLog(self.path) as wal:
                total, errors = self.run_concurrent(wal, threads=16, per_thread=25)
                self.assertEqual(errors, [])
                self.assertEqual(wal.last_lsn, total)
                got = wal.read_from(1)
        self.assertEqual([l for l, _ in got], list(range(1, total + 1)))
        self.assertLess(fsync_count[0], total // 4,
                        "没有攒批：%d 条记录刷了 %d 次" % (total, fsync_count[0]))

    def test_single_writer_still_durable_each_call(self):
        """低负载时逐条刷盘，不为了攒批拖着不刷。"""
        with WriteAheadLog(self.path) as wal:
            for i in range(5):
                wal.append(b"r%d" % i)
        with WriteAheadLog(self.path) as wal:
            self.assertEqual([p for _, p in wal.read_from(1)],
                             [b"r%d" % i for i in range(5)])


class TestAckTiming(GroupCommitCase):
    def test_append_blocks_until_flush_completes(self):
        """刷盘被卡住时 append 不许返回；放行后正常拿到 LSN。"""
        gate = threading.Event()
        real_fsync = os.fsync

        def gated_fsync(fd):
            gate.wait(5)
            return real_fsync(fd)

        with mock.patch("os.fsync", gated_fsync):
            with WriteAheadLog(self.path) as wal:
                result = []

                def writer():
                    result.append(wal.append(b"blocked"))

                t = threading.Thread(target=writer)
                t.start()
                time.sleep(0.2)
                self.assertTrue(t.is_alive(), "刷盘没完成 append 就返回了")
                self.assertEqual(result, [])
                gate.set()
                t.join(5)
                self.assertEqual(result, [1])


class TestFlushFailure(GroupCommitCase):
    def test_fsync_failure_fails_everyone_in_batch(self):
        """一次 fsync 失败，批内所有调用方都报错，之后的 append 也报错。"""
        boom = OSError("disk on fire")
        with mock.patch("os.fsync", mock.Mock(side_effect=boom)):
            with WriteAheadLog(self.path) as wal:
                _, errors = self.run_concurrent(wal, threads=4, per_thread=5)
                self.assertEqual(len(errors), 20, "有调用方没收到刷盘失败")
                for exc in errors:
                    self.assertIs(exc, boom)
                with self.assertRaises(OSError):
                    wal.append(b"after failure")

    def test_close_after_failure_does_not_hang(self):
        with mock.patch("os.fsync", mock.Mock(side_effect=OSError("boom"))):
            wal = WriteAheadLog(self.path)
            with self.assertRaises(OSError):
                wal.append(b"x")
        wal.close()  # 刷盘线程已退出，close 必须能正常收尾


class TestRecovery(GroupCommitCase):
    def test_torn_tail_after_batch_write_is_dropped(self):
        """攒批刷到一半被杀：重启截掉残尾，LSN 接上继续写。"""
        with WriteAheadLog(self.path) as wal:
            wal.append(b"good-1")
            wal.append(b"good-2")
        with open(self.path, "ab") as f:  # 模拟一批没刷完进程就没了
            f.write(b"\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x64half")
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.last_lsn, 2)
            self.assertEqual(wal.append(b"good-3"), 3)
            self.assertEqual([p for _, p in wal.read_from(1)],
                             [b"good-1", b"good-2", b"good-3"])

    def test_replay_order_matches_write_order_under_concurrency(self):
        with WriteAheadLog(self.path) as wal:
            total, errors = self.run_concurrent(wal)
            self.assertEqual(errors, [])
        with WriteAheadLog(self.path) as wal:
            got = wal.read_from(1)
            self.assertEqual([l for l, _ in got], list(range(1, total + 1)))
            self.assertEqual(sorted(p for _, p in got),
                             sorted(b"t%d-%d" % (t, i)
                                    for t in range(8) for i in range(25)))


if __name__ == "__main__":
    unittest.main()
