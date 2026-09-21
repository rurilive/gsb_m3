"""断点续传、去重丢弃、半截水位判废与有界缓冲背压的测试。"""

import os
import tempfile
import threading
import time
import unittest

from resumex.stream import (
    BoundedBuffer,
    DedupSink,
    MemorySink,
    MemorySource,
    Record,
    StreamRunner,
    WatermarkStore,
)


class RecordingSource:
    """记下每次 fetch 的 after_seq，并可喂指定返回批次的假来源。"""

    def __init__(self, batches):
        self._batches = list(batches)
        self.calls = []

    def fetch(self, after_seq, limit):
        self.calls.append((after_seq, limit))
        if self._batches:
            return self._batches.pop(0)
        return []


class FetchSignaledSource(MemorySource):
    """每次 fetch 后打点的来源，用来观测背压时取数是否停下。"""

    def __init__(self, records, fetch_event=None, fetch_gate=None):
        super().__init__(records)
        self.fetch_count = 0
        self._fetch_event = fetch_event
        self._fetch_gate = fetch_gate

    def fetch(self, after_seq, limit):
        if self._fetch_gate is not None:
            self._fetch_gate.wait(timeout=5)
        batch = super().fetch(after_seq, limit)
        self.fetch_count += 1
        if self._fetch_event is not None:
            self._fetch_event.set()
        return batch


class TmpLogMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "wm.log")

    def tearDown(self):
        self.tmp.cleanup()


class WatermarkStoreTest(TmpLogMixin, unittest.TestCase):

    def test_load_missing_file_is_zero(self):
        store = WatermarkStore(self.path, fsync=False)
        self.assertEqual(store.load(), 0)
        self.assertEqual(store.points(), [])

    def test_save_keeps_multiple_points_and_returns_latest(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(2, pushed=2, ts=1.0)
        store.save(4, pushed=4, ts=2.0)
        store.save(6, pushed=6, ts=3.0)
        again = WatermarkStore(self.path, fsync=False)
        self.assertEqual(again.load(), 6)
        seqs = [point[0] for point in again.points()]
        self.assertEqual(seqs, [2, 4, 6])
        self.assertEqual(again.pushed, 6)

    def test_save_rejects_non_advancing_watermark(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(5)
        with self.assertRaises(ValueError):
            store.save(4)
        with self.assertRaises(ValueError):
            store.save(5)

    def test_half_written_tail_is_rejected_and_truncated(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(3, pushed=3, ts=1.0)
        store.save(5, pushed=5, ts=2.0)
        with open(self.path, "rb") as fh:
            good = fh.read()
        # 崩溃在写一条新水位的半道：只有正文、没有校验和与换行
        with open(self.path, "ab") as fh:
            fh.write(b"RXC1\t7\t7\t9.0\tdead")
        reloaded = WatermarkStore(self.path, fsync=False)
        self.assertEqual(reloaded.load(), 5)
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), good)

    def test_bad_checksum_line_is_rejected(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(3)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("RXC1\t9\t9\t0.0\tdeadbeef\n")
        reloaded = WatermarkStore(self.path, fsync=False)
        self.assertEqual(reloaded.load(), 3)

    def test_garbage_prefix_rejects_everything(self):
        with open(self.path, "wb") as fh:
            fh.write(b"not a watermark\n")
        reloaded = WatermarkStore(self.path, fsync=False)
        self.assertEqual(reloaded.load(), 0)

    def test_non_monotonic_line_stops_scan(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(3)
        good_bytes = os.path.getsize(self.path)
        store.save(5)
        # 手工把第二个点改回小序号，它及其后全部判废
        with open(self.path, "rb") as fh:
            first_line = fh.readline()
        with open(self.path, "wb") as fh:
            fh.write(first_line)
            fh.write(b"RXC1\t2\t2\t0.0\t00000000\n")
        reloaded = WatermarkStore(self.path, fsync=False)
        self.assertEqual(reloaded.load(), 3)
        self.assertEqual(os.path.getsize(self.path), good_bytes)


class DedupSinkTest(unittest.TestCase):
    def test_duplicate_and_late_records_are_dropped(self):
        sink = DedupSink(initial_watermark=5)
        watermark = sink.push(
            [Record(3, "late"), Record(5, "dup"), Record(6, "new"), Record(6, "dup-in-batch")]
        )
        self.assertEqual(watermark, 6)
        self.assertEqual(sink.received(), [Record(6, "new")])
        self.assertEqual(sink.stats()["dropped"], 3)

    def test_watermark_only_advances(self):
        sink = DedupSink()
        sink.push([Record(5, "a")])
        sink.push([Record(2, "low"), Record(4, "lower")])
        self.assertEqual(sink.watermark, 5)
        self.assertEqual(sink.stats()["dropped"], 2)
        with self.assertRaises(ValueError):
            sink.adopt_watermark(4)
        sink.adopt_watermark(7)
        self.assertEqual(sink.watermark, 7)

    def test_negative_initial_watermark_rejected(self):
        with self.assertRaises(ValueError):
            DedupSink(initial_watermark=-1)


class ResumeRunnerTest(TmpLogMixin, unittest.TestCase):

    def _runner(self, source, sink, **kwargs):
        ticks = iter(float(n) for n in range(10000))
        store = WatermarkStore(self.path, fsync=False)
        runner = StreamRunner(
            source, sink, batch_size=2, clock=lambda: next(ticks), store=store, **kwargs
        )
        return runner, store

    def test_restart_continues_from_confirmed_watermark(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        sink = DedupSink()
        runner, store = self._runner(source, sink)
        self.assertEqual(runner.run(), 3)
        self.assertEqual([point[0] for point in store.points()], [2, 3])

        # “重启”：同一份水位文件、全新来源（重放旧记录）+ 新追加
        source2 = MemorySource([(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, "e")])
        sink2 = DedupSink()
        runner2, store2 = self._runner(source2, sink2)
        self.assertEqual(sink2.watermark, 3)  # 启动先认水位
        self.assertEqual(runner2.progress()["pushed"], 3)
        moved = runner2.run()
        self.assertEqual(moved, 2)
        self.assertEqual(sink2.received(), [Record(4, "d"), Record(5, "e")])
        self.assertEqual(sink2.stats()["dropped"], 0)
        self.assertEqual(store2.load(), 5)

    def test_first_fetch_uses_stored_watermark(self):
        store = WatermarkStore(self.path, fsync=False)
        store.save(4, pushed=4, ts=1.0)
        source = RecordingSource([[Record(5, "e")]])
        sink = DedupSink()
        runner = StreamRunner(source, sink, batch_size=2, store=store)
        self.assertEqual(sink.watermark, 4)
        runner.run()
        self.assertEqual(source.calls[0], (4, 2))  # 启动先认水位，再从水位之后取

    def test_duplicates_returned_by_source_are_dropped_and_counted(self):
        # 已确认到 4，来源不可靠地重放/乱序回水位以下的记录，下游照丢并计数
        WatermarkStore(self.path, fsync=False).save(4, pushed=4, ts=0.0)
        source = RecordingSource(
            [[Record(3, "late"), Record(4, "dup")], [Record(5, "new")]]
        )
        sink = DedupSink()
        runner, _ = self._runner(source, sink)
        runner.run()
        self.assertEqual(sink.received(), [Record(5, "new")])
        self.assertEqual(runner.progress()["dropped"], 2)
        self.assertEqual(runner.progress()["pushed"], 5)  # 4 条恢复 + 新推 1 条
        self.assertEqual(runner.progress()["last_seq"], 5)

    def test_watermark_not_persisted_before_sink_accepts(self):
        class FailingSink(DedupSink):
            def push(self, records):
                raise RuntimeError("sink down")

        source = MemorySource([(1, "a")])
        runner, store = self._runner(source, FailingSink())
        with self.assertRaises(RuntimeError):
            runner.run()
        self.assertEqual(store.load(), 0)
        self.assertFalse(os.path.exists(self.path))


class BackpressureTest(TmpLogMixin, unittest.TestCase):

    def test_buffer_full_blocks_source_and_counts_it(self):
        source = FetchSignaledSource([(seq, "x") for seq in range(1, 13)])
        release = threading.Event()
        first_batch = threading.Event()
        blocked = threading.Event()

        def pre_push(batch):
            if batch[0].seq == 1:
                first_batch.set()
                release.wait(timeout=5)

        def on_block():
            blocked.set()

        runner = StreamRunner(
            source,
            DedupSink(),
            batch_size=2,
            store=WatermarkStore(self.path, fsync=False),
            buffer_size=2,
            on_block=on_block,
            pre_push=pre_push,
        )
        done = threading.Event()
        result = {}

        def go():
            try:
                result["moved"] = runner.run()
            finally:
                done.set()

        worker = threading.Thread(target=go)
        worker.start()

        try:
            self.assertTrue(first_batch.wait(timeout=5))
            self.assertTrue(blocked.wait(timeout=5))
            # 背压期间：缓冲满，来源侧挂起，取数次数稳定（最多到塞满缓冲那次）
            time.sleep(0.05)
            fetch_when_blocked = source.fetch_count
            time.sleep(0.05)
            self.assertEqual(source.fetch_count, fetch_when_blocked)
            self.assertLessEqual(fetch_when_blocked, 3)
            self.assertGreaterEqual(runner.progress()["blocked"], 1)
        finally:
            release.set()
            self.assertTrue(done.wait(timeout=5))
            worker.join(timeout=5)
        progress = runner.progress()
        self.assertEqual(result["moved"], 12)
        self.assertEqual(progress["last_seq"], 12)
        self.assertGreaterEqual(progress["blocked"], 1)

    def test_bounded_buffer_blocks_then_drains(self):
        seen = []
        buffer = BoundedBuffer(1, on_block=lambda: seen.append(True))

        def fill():
            buffer.put("a")
            buffer.put("b")  # 必须等取走才能进
            buffer.put(None)

        worker = threading.Thread(target=fill)
        worker.start()
        time.sleep(0.05)
        self.assertEqual(buffer.get(), "a")
        self.assertEqual(buffer.get(), "b")
        self.assertIsNone(buffer.get())
        worker.join(timeout=5)
        self.assertEqual(seen, [True, True])
        self.assertEqual(buffer.blocked, 2)

    def test_invalid_buffer_size_rejected(self):
        with self.assertRaises(ValueError):
            StreamRunner(MemorySource(), MemorySink(), batch_size=2, buffer_size=0)


if __name__ == "__main__":
    unittest.main()
