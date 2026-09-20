"""断点续传、去重丢弃、半截水位拒读与有界背压的新行为测试。"""

import os
import tempfile
import threading
import time
import unittest

from resumex.checkpoint import WatermarkLog
from resumex.stream import MemorySink, MemorySource, Record, StreamRunner, WatermarkSink


class WatermarkLogFile:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "watermarks.log")

    def tearDown(self):
        self._tmp.cleanup()


class TestWatermarkLog(WatermarkLogFile, unittest.TestCase):
    def test_missing_log_loads_zero(self):
        self.assertEqual(WatermarkLog(self.path).load(), 0)

    def test_commit_then_reload_keeps_watermark(self):
        store = WatermarkLog(self.path)
        store.commit(3, stamped_at=10.0)
        store.commit(7, stamped_at=20.0)
        reloaded = WatermarkLog(self.path)
        self.assertEqual(reloaded.load(), 7)
        self.assertEqual([seq for seq, _ in reloaded.points()], [3, 7])

    def test_commit_never_goes_backwards(self):
        store = WatermarkLog(self.path)
        store.commit(9, stamped_at=1.0)
        self.assertEqual(store.commit(4, stamped_at=2.0), 9)
        self.assertEqual(WatermarkLog(self.path).load(), 9)

    def test_keeps_multiple_points_and_compacts(self):
        store = WatermarkLog(self.path, keep=3)
        for seq in range(1, 8):
            store.commit(seq, stamped_at=float(seq))
        reloaded = WatermarkLog(self.path, keep=3)
        self.assertEqual([seq for seq, _ in reloaded.points()], [5, 6, 7])
        self.assertEqual(reloaded.load(), 7)

    def test_truncated_tail_line_is_rejected(self):
        store = WatermarkLog(self.path)
        store.commit(5, stamped_at=11.0)
        with open(self.path, "ab") as handle:
            handle.write(b"resumex-v1\t6\t12.0\tdeadbeef-half-written")
        reloaded = WatermarkLog(self.path)
        self.assertEqual(reloaded.load(), 5)
        self.assertEqual([seq for seq, _ in reloaded.points()], [5])

    def test_garbage_lines_are_rejected(self):
        with open(self.path, "wb") as handle:
            handle.write(b"not a watermark\n")
            handle.write(b"resumex-v1\tNaN\t1.0\t00\n")
        self.assertEqual(WatermarkLog(self.path).load(), 0)

    def test_checksum_mismatch_line_is_rejected(self):
        store = WatermarkLog(self.path)
        store.commit(4, stamped_at=3.0)
        with open(self.path, "rb") as handle:
            good = handle.read()
        tampered = good.replace(b"\t4\t", b"\t8\t", 1)
        with open(self.path, "wb") as handle:
            handle.write(tampered)
        self.assertEqual(WatermarkLog(self.path).load(), 0)


class TestWatermarkSink(unittest.TestCase):
    def test_duplicate_seq_is_dropped(self):
        sink = WatermarkSink()
        sink.push([Record(1, "a"), Record(2, "b")])
        moved = sink.push([Record(2, "b-again"), Record(3, "c")])
        self.assertEqual(moved, 3)
        self.assertEqual(sink.dropped, 1)
        self.assertEqual(sink.received(), [Record(1, "a"), Record(2, "b"), Record(3, "c")])
        self.assertEqual(sink.stats()["dropped"], 1)

    def test_out_of_order_below_watermark_is_dropped(self):
        sink = WatermarkSink(watermark=5)
        moved = sink.push([Record(3, "late"), Record(5, "dup"), Record(6, "new")])
        self.assertEqual(moved, 6)
        self.assertEqual(sink.dropped, 2)
        self.assertEqual(sink.received(), [Record(6, "new")])

    def test_align_never_goes_backwards(self):
        sink = WatermarkSink(watermark=8)
        self.assertEqual(sink.align(3), 8)
        self.assertEqual(sink.align(12), 12)


class TestRestartResume(WatermarkLogFile, unittest.TestCase):
    def _runner(self, source, sink):
        return StreamRunner(
            source, sink, batch_size=3, store=WatermarkLog(self.path)
        )

    def test_restart_resumes_from_persisted_watermark(self):
        source = MemorySource([(seq, "p%d" % seq) for seq in range(1, 11)])
        sink = WatermarkSink()

        first = self._runner(source, sink)
        self.assertEqual(first.run(), 10)
        self.assertEqual(sink.watermark, 10)

        source.append(11, "p11")
        second_sink = WatermarkSink()
        second = self._runner(source, second_sink)
        self.assertEqual(second.progress()["last_seq"], 10)
        self.assertEqual(second.run(), 1)
        self.assertEqual(second_sink.received(), [Record(11, "p11")])
        self.assertEqual(second.progress()["last_seq"], 11)

    def test_watermark_read_before_first_fetch(self):
        store = WatermarkLog(self.path)
        store.commit(4, stamped_at=1.0)

        seen = []

        class TracingSource(MemorySource):
            def fetch(self, after_seq, limit):
                seen.append(after_seq)
                return super().fetch(after_seq, limit)

        source = TracingSource([(seq, "x") for seq in range(1, 7)])
        runner = StreamRunner(
            source, WatermarkSink(), batch_size=2, store=store
        )
        runner.run()
        self.assertEqual(seen[0], 4)

    def test_replayed_records_below_watermark_are_dropped_not_refed(self):
        store = WatermarkLog(self.path)
        store.commit(3, stamped_at=1.0)
        sink = WatermarkSink()
        StreamRunner(
            MemorySource([(1, "a"), (2, "b"), (3, "c"), (4, "d")]),
            sink,
            batch_size=2,
            store=store,
        ).run()
        self.assertEqual(sink.received(), [Record(4, "d")])
        self.assertEqual(sink.dropped, 0)


class CountingSource(MemorySource):
    def __init__(self, records):
        super().__init__(records)
        self.fetch_calls = 0

    def fetch(self, after_seq, limit):
        self.fetch_calls += 1
        return super().fetch(after_seq, limit)


class SlowSink(MemorySink):
    """第一批先阻塞，放行前调用方可断言上游已被背顶住。"""

    def __init__(self):
        super().__init__()
        self.allow = threading.Event()
        self.proceeded = threading.Event()

    def push(self, records):
        if self._batches == 0:
            self.proceeded.set()
            self.allow.wait(timeout=5)
        return super().push(records)


class TestBackpressure(unittest.TestCase):
    def test_buffer_cap_stops_fetching_and_counts_blocking(self):
        source = CountingSource([(seq, "p%d" % seq) for seq in range(1, 13)])
        sink = SlowSink()
        runner = StreamRunner(
            source, sink, batch_size=2, buffer_size=2
        )

        done = []

        def drive():
            done.append(runner.run())

        thread = threading.Thread(target=drive)
        thread.start()
        self.assertTrue(sink.proceeded.wait(timeout=2))
        # 下游卡住时：容量 2 批，缓冲填满后进入阻塞等待，再多一次都不取。
        deadline = time.time() + 2
        while time.time() < deadline:
            if runner.progress()["blocked"] >= 1:
                break
            time.sleep(0.01)
        self.assertGreaterEqual(runner.progress()["blocked"], 1)
        self.assertEqual(source.fetch_calls, 2)

        sink.allow.set()
        thread.join(timeout=5)
        self.assertEqual(done, [12])
        self.assertEqual(sink.watermark, 12)
        progress = runner.progress()
        self.assertGreaterEqual(progress["blocked"], 1)
        self.assertGreaterEqual(progress["blocked_for"], 0.0)

    def test_buffered_run_drains_everything_with_store(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "wm.log")
        source = MemorySource([(seq, "x") for seq in range(1, 7)])
        sink = WatermarkSink()
        runner = StreamRunner(
            source,
            sink,
            batch_size=3,
            store=WatermarkLog(path),
            buffer_size=2,
        )
        self.assertEqual(runner.run(), 6)
        source.append(7, "x7")
        self.assertEqual(runner.run(), 1)
        self.assertEqual(sink.watermark, 7)
        self.assertEqual(WatermarkLog(path).load(), 7)

    def test_invalid_buffer_size_raises(self):
        with self.assertRaises(ValueError):
            StreamRunner(MemorySource(), MemorySink(), buffer_size=-1)


if __name__ == "__main__":
    unittest.main()
