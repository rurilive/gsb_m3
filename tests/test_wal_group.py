"""组提交新行为：攒批刷盘、刷盘前不返回、整批同成败、顺序与唤醒。"""
import os
import struct
import tempfile
import threading
import time
import unittest
from unittest import mock

from walg import WriteAheadLog

HEAD = struct.Struct(">QI")


class WalGroupCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "wal.log")


class TestBatching(WalGroupCase):
    def test_concurrent_appends_share_fsyncs(self):
        """200 条并发 append 只应触发少量 fsync，且数据一条不少。"""
        threads, per_thread = 8, 25
        barrier = threading.Barrier(threads)
        syncs = []
        real_fsync = os.fsync

        def counting_fsync(fd):
            syncs.append(1)
            return real_fsync(fd)

        with mock.patch("os.fsync", counting_fsync):
            with WriteAheadLog(self.path, group_wait=0.02) as wal:
                def worker(tag):
                    barrier.wait()
                    for i in range(per_thread):
                        wal.append(b"t%d-%d" % (tag, i))

                pool = [threading.Thread(target=worker, args=(t,))
                        for t in range(threads)]
                for t in pool:
                    t.start()
                for t in pool:
                    t.join()

        self.assertGreater(len(syncs), 0)
        self.assertLess(len(syncs), threads * per_thread // 2,
                        "并发写入几乎没有凑批，fsync 次数=%d" % len(syncs))
        with WriteAheadLog(self.path) as wal:
            got = wal.read_from(1)
            self.assertEqual(wal.last_lsn, threads * per_thread)
            self.assertEqual(len(got), threads * per_thread)

    def test_batch_size_caps_a_batch(self):
        """凑满 batch_size 立即开刷，不等宽限窗口。"""
        syncs = []
        real_fsync = os.fsync

        def counting_fsync(fd):
            syncs.append(1)
            return real_fsync(fd)

        with mock.patch("os.fsync", counting_fsync):
            with WriteAheadLog(self.path, batch_size=2, group_wait=0.05) as wal:
                first = wal.append(b"a")
                second = wal.append(b"b")
                third = wal.append(b"c")

        self.assertEqual([first, second, third], [1, 2, 3])
        self.assertGreaterEqual(len(syncs), 2)
        with WriteAheadLog(self.path) as wal:
            self.assertEqual([p for _, p in wal.read_from(1)],
                             [b"a", b"b", b"c"])


class TestDurability(WalGroupCase):
    def test_append_does_not_return_before_sync(self):
        """组提交下，append 返回时本批刷盘也必须已经完成。"""
        synced = []
        real_fsync, real_fdatasync = os.fsync, os.fdatasync

        def spy_fsync(fd):
            synced.append(1)
            return real_fsync(fd)

        def spy_fdatasync(fd):
            synced.append(1)
            return real_fdatasync(fd)

        with mock.patch("os.fsync", spy_fsync), \
                mock.patch("os.fdatasync", spy_fdatasync):
            with WriteAheadLog(self.path) as wal:
                for i in range(20):
                    before = len(synced)
                    wal.append(b"r%d" % i)
                    self.assertGreater(len(synced), before,
                                       "第 %d 条 append 返回前没有刷盘" % (i + 1))

    def test_leader_wait_is_bounded(self):
        """没人凑批时也不能被拖太久：宽限窗口到点就刷。"""
        with WriteAheadLog(self.path, group_wait=0.01) as wal:
            start = time.monotonic()
            wal.append(b"solo")
            self.assertLess(time.monotonic() - start, 0.5)


class TestBatchFailure(WalGroupCase):
    def test_fsync_failure_fails_whole_batch_and_recoverable(self):
        """一次 fsync 失败，同批所有调用方都得知道自己没成。"""
        results = {}
        release = threading.Event()
        entered = threading.Event()
        barrier = threading.Barrier(3)
        real_fsync = os.fsync

        def failing_fsync(fd):
            entered.set()
            release.wait(5)
            raise OSError("mock disk failure")

        with WriteAheadLog(self.path, group_wait=0.02) as wal:
            def worker(tag):
                barrier.wait()
                try:
                    results[tag] = ("ok", wal.append(b"w%d" % tag))
                except OSError as error:
                    results[tag] = ("err", error)

            pool = [threading.Thread(target=worker, args=(t,)) for t in range(3)]
            with mock.patch("os.fsync", failing_fsync):
                for t in pool:
                    t.start()
                self.assertTrue(entered.wait(5))
                release.set()
                for t in pool:
                    t.join()

            self.assertEqual(set(results), {0, 1, 2})
            self.assertTrue(all(kind == "err" for kind, _ in results.values()),
                            "整批必须一起失败: %r" % (results,))
            with self.assertRaises(OSError):
                wal.append(b"after")

        # 重启：模拟故障里 write 可能已进页缓存，残尾（无论截到哪）都必须
        # 被修成完整记录前缀；已确认的 LSN 不能错位，新 LSN 从其后接续。
        with WriteAheadLog(self.path) as wal:
            persisted = wal.read_from(1)
            self.assertEqual([l for l, _ in persisted],
                             list(range(1, wal.last_lsn + 1)))
            next_lsn = wal.append(b"recovered")
            self.assertEqual(next_lsn, wal.last_lsn)
            self.assertEqual([p for _, p in wal.read_from(next_lsn)],
                             [b"recovered"])


class TestOrdering(WalGroupCase):
    def test_lsn_allocated_in_enqueue_order(self):
        """磁盘顺序 = 入队顺序；每个线程自己的 LSN 必须严格递增。"""
        threads, per_thread = 8, 50
        barrier = threading.Barrier(threads)
        per_worker = {}

        with WriteAheadLog(self.path) as wal:
            def worker(tag):
                lsns = []
                barrier.wait()
                for i in range(per_thread):
                    lsns.append(wal.append(b"t%d-%d" % (tag, i)))
                per_worker[tag] = lsns

            pool = [threading.Thread(target=worker, args=(t,))
                    for t in range(threads)]
            for t in pool:
                t.start()
            for t in pool:
                t.join()

            all_lsns = [l for lsns in per_worker.values() for l in lsns]
            self.assertEqual(sorted(all_lsns), list(range(1, threads * per_thread + 1)))
            for lsns in per_worker.values():
                self.assertEqual(lsns, sorted(lsns))
            self.assertEqual(len(set(all_lsns)), len(all_lsns))

            got = wal.read_from(1)
            for _, payload in got:
                tag, seq = payload[1:].split(b"-", 1)
                self.assertEqual(b"t%d-%s" % (int(tag), seq), payload)
            self.assertEqual(sorted(l for l, _ in got), sorted(all_lsns))

    def test_concurrent_replay_order_matches_disk_order(self):
        """刷盘途中读重放，看到的也必须是 LSN 升序的完整记录。"""
        stop = threading.Event()
        errors = []

        with WriteAheadLog(self.path, group_wait=0.001) as wal:
            def writer(tag):
                i = 0
                while not stop.is_set():
                    wal.append(b"%d-%d" % (tag, i))
                    i += 1

            def reader():
                last = 0
                while not stop.is_set():
                    try:
                        got = wal.read_from(1)
                    except Exception as error:  # noqa: BLE001 - 任何异常都算违规
                        errors.append(error)
                        return
                    lsns = [l for l, _ in got]
                    if lsns != sorted(lsns) or len(set(lsns)) != len(lsns):
                        errors.append(AssertionError("重放乱序: %r" % lsns[:10]))
                        return
                    if got and got[-1][0] < last:
                        errors.append(AssertionError("LSN 回退"))
                        return
                    last = got[-1][0] if got else last

            pool = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
            pool.append(threading.Thread(target=reader))
            for t in pool:
                t.start()
            time.sleep(0.3)
            stop.set()
            for t in pool:
                t.join()

        self.assertEqual(errors, [])


class TestClose(WalGroupCase):
    def test_close_waits_for_inflight_batch(self):
        """close 必须先把已接收、在飞的批刷完，不能丢。"""
        count = 40
        done = []
        start = threading.Barrier(count + 1)

        wal = WriteAheadLog(self.path, group_wait=0.05)

        def worker(tag):
            start.wait()
            done.append(wal.append(b"c%d" % tag))

        pool = [threading.Thread(target=worker, args=(t,)) for t in range(count)]
        for t in pool:
            t.start()
        start.wait()
        deadline = time.monotonic() + 5
        while len(wal._pending) < count and time.monotonic() < deadline:
            time.sleep(0.001)
        self.assertEqual(len(wal._pending), count)
        wal.close()  # 落在宽限窗内：已接收的批必须刷完
        for t in pool:
            t.join()

        self.assertEqual(len(done), count)
        with WriteAheadLog(self.path) as reopened:
            self.assertEqual(reopened.last_lsn, count)
            self.assertEqual(len(reopened.read_from(1)), count)


class TestTornTail(WalGroupCase):
    def test_half_record_after_grouped_writes_is_truncated(self):
        with WriteAheadLog(self.path) as wal:
            for i in range(20):
                wal.append(b"g%d" % i)
        with open(self.path, "ab") as f:
            f.write(HEAD.pack(21, 100) + b"half")
        with WriteAheadLog(self.path) as wal:
            self.assertEqual(wal.last_lsn, 20)
            self.assertEqual([p for _, p in wal.read_from(1)],
                             [b"g%d" % i for i in range(20)])
            self.assertEqual(wal.append(b"g20"), 21)


if __name__ == "__main__":
    unittest.main()
